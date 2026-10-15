"""Server-owned focus sessions. The public state is an explicit numeric/boolean whitelist."""
import json
import math
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from focus_reader import Reader

EYES_STALE_S = 2
RELIEF_S = 180
NAME_DISTRACTIONS = True
SPEECH_VOICE = 'Daniel'
DEFER_TIMEOUT_S = 45
INTENT_MAX_CHARS = 4000
INTENT_LABEL_WORDS = 5
INTENT_LABEL_CHARS = 60
TICK_S = 1.0
GRACE_S = 0.8
MIN_DURATION_S = 1
REPORT_DECIMALS = 1
DEFAULT_DURATION_S = 30 * 60
DEFAULT_NAG_S = 30
MIN_INTERVAL_S = 3
MAX_DURATION_S = 12 * 60 * 60
CLEAN_THRESHOLD = 0.85
SECONDS_PER_MINUTE = 60
LEDGER_PATH = Path(__file__).resolve().parent / 'ledger-focus.json'
PRIVATE_MODE = 0o600
CARD_PATH = Path(__file__).resolve().parent / '.local' / 'JarvisFocusCard'
CARD_STOP_TIMEOUT_S = 2
POOLS = (
    ('A small detour, sir. Back to the task.', 'Your task is waiting. Shall we return?',
     'Sir, the assignment awaits.', 'Back to your chosen work, sir.'),
    ('The detour is becoming a holiday. Back to work.', 'Focus, sir. That was not the assignment.',
     'Sir, we have wandered far enough.', 'The task has not finished itself, sir.'),
    ('We are now professionally avoiding the task. Return to it.', 'Your future self has lodged a complaint. Back to work.',
     'Sir, the detours are becoming the project.', 'Enough reconnaissance, sir. Back to work.'))
NAMED_POOLS = (
    ('Sir, {label} can wait.', 'A detour into {label}, sir. Back to the task.',
     '{label} will survive your absence, sir.', 'Sir, leave {label} and return to your work.'),
    ('Still in {label}, sir. It is starting to look deliberate.', '{label} is becoming a holiday, sir.',
     'Sir, {label} was not the assignment.', 'Enough time in {label}, sir. Back to work.'),
    ('Sir, {label} is becoming the project.', 'We are now professionally browsing {label}, sir.',
     'Your future self has lodged a complaint about {label}, sir.', 'Leave {label}, sir. The task needs you.'))
DRILL_POOLS = (
    ('Close the detour into {label}, sir. Execute the task.', 'Eyes off {label}, sir. Back to work.',
     'Leave {label}, sir. Move.', 'Sir, {label} is off mission. Return.'),
    ('Enough {label}, sir. Execute.', 'Sir, disengage from {label}. Now.',
     '{label} is costing work time, sir. Move.', 'Back from {label}, sir. Stay on task.'),
    ('Sir, end the {label} detour. No more delay.', 'Leave {label}. Finish what you started, sir.',
     'Sir, {label} has had enough attention. Work.', 'Disengage from {label}, sir. The assignment stands.'))
PUBLIC_KEYS = frozenset({'active', 'armed', 'lock_deferred', 'app_only', 'has_intent', 'paused', 'drifting', 'excused', 'known', 'home',
    'remaining_s', 'planned_s', 'elapsed_s', 'on_target_s', 'drift_s', 'drifts', 'tier',
    'present', 'head_down', 'slouched', 'eyes_active', 'nag_s', 'snooze_s', 'streak', 'completed', 'aborted', 'ledger_ok', 'speaking'})
NUMBER_WORDS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
    'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
    'sixty': 60, 'ninety': 90}
LEDGER_KEYS = ('sessions', 'aborted', 'planned_s', 'on_target_s', 'drifts', 'streak')


RETARGET_PATTERN = r"(?:(?:okay|ok)\s+)?(?:(?:i'm|i’m|im|i am) (?:gonna need|going to need|need) you to )?(?:lock (?:on )?this tab|keep me in this tab|this is the tab|stay on this tab)"


def parse_command(text):
    text = re.sub(r'[,.!?]', '', text.casefold()).strip()
    text = re.sub(r'^(?:(?:hey )?jarvis\s+)?(?:please\s+)?', '', text)
    if re.fullmatch(RETARGET_PATTERN, text):
        return 'retarget', None
    if text in ('drill sergeant mode', 'normal mode'):
        return ('drill' if text.startswith('drill') else 'normal'), None
    for word in sorted(NUMBER_WORDS, key=len, reverse=True):
        text = re.sub(r'\b' + word + r'\b', str(NUMBER_WORDS[word]), text)
    text = re.sub(r'\b(20|30|40|50|60)\s+(\d)\b', lambda m: str(int(m[1])+int(m[2])), text)
    match = re.fullmatch(r'(\d+) (seconds?|minutes?|hours?) on this', text)
    action = 'start'
    if not match:
        for action, pattern in (
            ('nag', r'call me out every (\d+) (seconds?|minutes?)'),
            ('snooze', r'(?:give me|snooze(?: for)?) (\d+) (seconds?|minutes?)'),
            ('extend', r'(?:extend(?: focus| the session)?(?: by)?|add) (\d+) (seconds?|minutes?|hours?)')):
            match = re.fullmatch(pattern, text)
            if match:
                break
    if match:
        multiplier = SECONDS_PER_MINUTE if match[2].startswith('minute') else SECONDS_PER_MINUTE ** 2 if match[2].startswith('hour') else 1
        return action, int(match[1]) * multiplier
    for action, pattern in (
        ('start', r'(?:start )?focus(?: session)?'),
        ('pause', r'pause(?: focus| the session)?'),
        ('resume', r'resume(?: focus| the session)?'),
        ('end', r'(?:end|finish)(?: focus| the session)?'),
        ('abort', r'(?:abort|cancel)(?: focus| the session)?'),
        ('excuse', r"(?:it's|its|it is) (?:okay|ok)(?: .*)?")):
        if re.fullmatch(pattern, text):
            return action, None
    return None


ATTENTION_S = 3


class Speaker:
    def __init__(self):
        self.pending = queue.Queue()
        self.gate = threading.Lock()
        self.generation = 0
        self.process = None
        self.speaking = False
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        with self.gate:
            self.generation += 1
            while True:
                try:
                    self.pending.get_nowait()
                    self.pending.task_done()
                except queue.Empty:
                    break
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def busy(self):
        return self.speaking or not self.pending.empty()

    def __call__(self, text):
        with self.gate:
            self.pending.put((self.generation, text))

    def _run(self):
        while True:
            generation, text = self.pending.get()
            self.speaking = True
            try:
                with self.gate:
                    if generation != self.generation:
                        continue
                    self.process = subprocess.Popen(['/usr/bin/say', '-v', SPEECH_VOICE, text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.process.wait()
            except OSError:
                pass
            finally:
                self.process = None
                del text
                self.speaking = False
                self.pending.task_done()


class Focus:
    def __init__(self, reader=None, clock=time.monotonic, speak=None, ledger=LEDGER_PATH):
        self.reader, self.clock = reader or Reader(), clock
        self.speak = speak if speak is not None else Speaker()
        self.path = Path(ledger)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.card = None
        self.ledger = dict.fromkeys(LEDGER_KEYS, 0)
        self.ledger_ok = True
        try:
            loaded = json.loads(self.path.read_text())
            if set(loaded) != set(LEDGER_KEYS) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in loaded.values()):
                raise ValueError
            self.ledger = loaded
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            self.ledger_ok = False
        self.active = self.armed = self.paused = self.completed = self.aborted = False
        self.known = self.home = False
        self.planned = self.elapsed = self.on_target = self.drift_time = 0.0
        self.drifts = self.tier = 0
        self.nag = DEFAULT_NAG_S
        self.snooze_until = 0.0
        self.last = self.clock()
        self.away_since = None
        self.excused = self.counted = False
        self.excursion_time = 0.0
        self.next_nag = 0.0
        self.defer_since = 0.0
        self.app_only = False
        self.intent = ''
        self.drill = False
        self.callouts = 0
        self.pool_positions = [0] * len(POOLS)
        self.muted = False
        self.relief_until = 0.0
        self.attention_until = 0.0
        self.eyes = dict(present=False, head_down=False, slouched=False, eyes_active=False)
        self.eyes_seen = 0
        self.eye_counted = False

    def say(self, text):
        if not self.muted and self.clock() >= max(self.relief_until, self.attention_until):
            self.speak(text)

    def attention(self):
        with self.lock:
            self.attention_until = self.clock() + ATTENTION_S
            if isinstance(self.speak, Speaker):
                self.speak.cancel()

    def relief(self):
        with self.lock:
            self.relief_until = self.clock() + RELIEF_S
            if isinstance(self.speak, Speaker):
                self.speak.cancel()

    def eyes_update(self, body):
        keys = {'present', 'head_down', 'slouched', 'eyes_active'}
        if set(body) != keys or any(type(v) is not bool for v in body.values()):
            raise ValueError('Eyes accepts only posture booleans.')
        with self.lock:
            self.eyes = dict(body)
            self.eyes_seen = self.clock()
            if not body['head_down'] or not body['eyes_active']:
                self.eye_counted = False
            elif self.active and not self.paused and not self.armed and not self.eye_counted:
                self.drifts += 1
                self.eye_counted = True

    def state(self):
        with self.lock:
            if self.clock()-self.eyes_seen >= EYES_STALE_S:
                self.eyes = dict(present=False, head_down=False, slouched=False, eyes_active=False)
                self.eye_counted = False
            # Never serialize __dict__, the reader, samples, or arbitrary client data.
            return dict(**self.eyes, active=self.active, armed=self.armed, lock_deferred=self.armed,
                app_only=self.app_only, has_intent=bool(self.intent), paused=self.paused,
                drifting=(self.counted and not self.excused and not self.home) or (self.active and self.eyes['eyes_active'] and self.eyes['head_down']), excused=self.excused,
                known=self.known, home=self.home, remaining_s=math.ceil(max(0, self.planned-self.elapsed)),
                planned_s=self.planned, elapsed_s=self.elapsed, on_target_s=self.on_target,
                drift_s=self.drift_time, drifts=self.drifts, tier=self.tier, nag_s=self.nag,
                snooze_s=math.ceil(max(0, max(self.snooze_until, self.relief_until)-self.clock())), streak=self.ledger['streak'],
                completed=self.completed, aborted=self.aborted, ledger_ok=self.ledger_ok,
                speaking=isinstance(self.speak, Speaker) and self.speak.busy())

    def _clear_excursion(self):
        self.away_since = None
        self.counted = self.excused = False
        self.excursion_time = 0.0
        self.tier = 0

    def tick(self):
        with self.lock:
            now = self.clock()
            dt = max(0, now - self.last)
            self.last = now
            if not self.active or self.paused:
                return
            fallback = self.armed and now-self.defer_since >= DEFER_TIMEOUT_S
            sample = self.reader.sample(arm=self.armed, settle=self.armed and not fallback, app_only=fallback, naming=NAME_DISTRACTIONS)
            self.known, self.home = sample['known'], sample['home']
            if not self.known:
                # A permission/query failure freezes accounting, never fabricates focus.
                return
            if self.armed:
                if not sample['locked']:
                    return
                self.armed = False
                self.app_only = fallback
                self.say('Locked on, sir.' if not fallback else 'App-only focus locked, sir.')
                self.last = self.clock()
                return
            dt = min(dt, max(0, self.planned-self.elapsed))
            self.elapsed += dt
            phone = self.eyes['eyes_active'] and self.eyes['head_down'] and now-self.eyes_seen < EYES_STALE_S
            safe = (sample['target'] or self.home) and not phone
            if phone:
                self.drift_time += dt
                if self.elapsed >= self.planned:
                    self._finish(False)
                return
            if safe:
                self.on_target += dt
                # Home is neutral, but only the actual target ends an excused excursion.
                if sample['target']:
                    if not self.counted and not self.excused:
                        self.drift_time = max(0, self.drift_time-self.excursion_time)
                        self.on_target += self.excursion_time
                    self._clear_excursion()
            elif self.excused:
                self.on_target += dt
            else:
                self.excursion_time += dt
                self.drift_time += dt
                if self.away_since is None:
                    self.away_since = now
                if now - self.away_since >= GRACE_S:
                    if not self.counted:
                        self.drifts += 1
                        self.counted = True
                        self.next_nag = now
                    if now >= self.next_nag and now >= max(self.snooze_until, self.relief_until) and not (isinstance(self.speak, Speaker) and self.speak.busy()):
                        self.tier = min(len(POOLS), self.tier+1)
                        self.say(self.callout(sample.get('label', '') if NAME_DISTRACTIONS else ''))
                        self.next_nag = now+self.nag
            if self.elapsed >= self.planned:
                self._finish(False)

    def callout(self, label):
        # Only counters persist: neither the sampled label nor rendered line is retained.
        first = self.callouts == 0
        self.callouts += 1
        if first and self.intent:
            if label:
                return f"Sir — {label} does not look like '{self.intent_label()}' to me."
            return f'Back to {self.intent_label()}, sir.'
        tier = self.tier - 1
        pool = (DRILL_POOLS if self.drill else NAMED_POOLS)[tier] if label else POOLS[tier]
        line = pool[self.pool_positions[tier] % len(pool)]
        self.pool_positions[tier] += 1
        return line.format(label=label)

    def intent_label(self):
        words = self.intent.split()
        label = ' '.join(words[:INTENT_LABEL_WORDS])[:INTENT_LABEL_CHARS]
        return label + ('…' if label != self.intent else '')

    def set_intent(self, text):
        with self.lock:
            if not self.active or self.intent or not isinstance(text, str) or not text.strip():
                raise ValueError('No focus answer is pending.')
            self.intent = ' '.join(text.split())[:INTENT_MAX_CHARS]
            return 'Noted, sir.'

    def _finish(self, aborted):
        self.active = self.armed = self.paused = False
        self.completed, self.aborted = not aborted, aborted
        clean = not aborted and self.on_target / max(MIN_DURATION_S, self.planned) >= CLEAN_THRESHOLD
        self.ledger['sessions'] += 1
        self.ledger['aborted'] += int(aborted)
        self.ledger['planned_s'] += self.planned
        self.ledger['on_target_s'] += self.on_target
        self.ledger['drifts'] += self.drifts
        self.ledger['streak'] = self.ledger['streak']+1 if clean else 0
        if self.ledger_ok:
            try:
                temporary = self.path.with_suffix('.tmp')
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, PRIVATE_MODE)
                with os.fdopen(fd, 'w') as output:
                    json.dump({key: self.ledger[key] for key in LEDGER_KEYS}, output)
                os.replace(temporary, self.path)
            except OSError:
                self.ledger_ok = False
        self.reader.clear()
        self._clear_excursion()
        report = (f"{'Aborted' if aborted else 'Session complete'}. {self.on_target/SECONDS_PER_MINUTE:.{REPORT_DECIMALS}f} minutes on target "
                  f"out of {self.planned/SECONDS_PER_MINUTE:.{REPORT_DECIMALS}f} planned. {self.drifts} drifts. Streak: {self.ledger['streak']}.")
        if self.intent:
            report += f' Focus: {self.intent_label()}.'
        if not self.ledger_ok:
            report += ' The aggregate ledger could not be saved.'
        self.say(report)
        return report

    def command(self, action, seconds=None, defer_lock=False, from_card=False):
        with self.lock:
            if action not in ('start', 'pause', 'resume', 'extend', 'abort', 'end', 'nag', 'snooze', 'excuse', 'retarget', 'drill', 'normal'):
                raise ValueError('Unknown focus command.')
            if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or not MIN_DURATION_S <= seconds <= MAX_DURATION_S):
                raise ValueError('Choose a duration between one second and twelve hours.')
            if action in ('extend', 'nag', 'snooze') and seconds is None:
                raise ValueError('Give a duration for that command.')
            if action == 'start':
                if self.active:
                    raise ValueError('A focus session is already running.')
                self.reader.clear()
                self.intent = ''
                self.app_only = False
                self.planned = seconds or DEFAULT_DURATION_S
                self.elapsed = self.on_target = self.drift_time = 0.0
                self.drifts = 0
                self.eye_counted = False
                self.callouts = 0
                self.pool_positions = [0] * len(POOLS)
                self._clear_excursion()
                self.snooze_until = 0.0
                self.completed = self.aborted = self.paused = False
                self.active = self.armed = True
                sample = self.reader.sample(arm=not defer_lock)
                self.known, self.home = sample['known'], sample['home']
                self.armed = not sample['locked']
                self.last = self.clock()
                self.defer_since = self.last
                message = ("Go to what you're working on and I'll lock on there. And what are we focusing on?" if self.armed else 'Focus started. Target locked. And what are we focusing on?')
            elif not self.active:
                raise ValueError('Start a focus session first.')
            elif action in ('drill', 'normal'):
                self.drill = action == 'drill'
                message = 'Drill-sergeant mode, sir.' if self.drill else 'Normal callouts, sir.'
            elif action == 'retarget':
                # Read into a fresh reader so a permission failure preserves the old target.
                candidate = Reader(self.reader._query)
                candidate._browser = self.reader._browser
                sample = candidate.sample(arm=True, from_card=from_card)
                if not sample['known']:
                    raise ValueError('I could not read the target, sir. Go to the tab and say "lock on this tab" again.')
                self.reader = candidate
                if not self.excused:
                    self.drift_time = max(0, self.drift_time-self.excursion_time)
                    self.on_target += self.excursion_time
                    self.drifts -= int(self.counted)
                self._clear_excursion()
                self.next_nag = self.snooze_until = 0.0
                self.known, self.home = sample['known'], sample['home']
                self.armed = not sample['locked']
                self.app_only = False
                self.last = self.defer_since = self.clock()
                message = "Go to it, sir — I'll lock on where you land." if self.armed else 'Locked on, sir.'
            elif action in ('abort', 'end'):
                return self._finish(action == 'abort')
            elif action == 'pause':
                self.paused = True
                message = 'Focus paused.'
            elif action == 'resume':
                self.paused = False
                self.last = self.clock()
                if self.away_since is not None:
                    self.away_since = self.last
                message = 'Focus resumed.'
            elif action == 'extend':
                if self.planned+seconds > MAX_DURATION_S:
                    raise ValueError('A session cannot exceed twelve hours.')
                self.planned += seconds
                message = 'Focus extended.'
            elif action == 'nag':
                self.nag = max(MIN_INTERVAL_S, seconds)
                self.next_nag = self.clock()+self.nag
                message = f'Callouts every {self.nag:g} seconds.'
            elif action == 'snooze':
                self.snooze_until = self.clock()+seconds
                message = f'Quiet for {seconds:g} seconds.'
            else:
                if self.away_since is not None and not self.excused:
                    self.drift_time = max(0, self.drift_time-self.excursion_time)
                    self.on_target += self.excursion_time
                    self.drifts -= int(self.counted)
                    self.counted = False
                    self.excused = True
                    message = 'Excursion refunded. Quiet until you return to your target.'
                else:
                    message = 'There is no current excursion to excuse.'
            return message

    def start_loop(self):
        def loop():
            deadline = self.clock()
            while not self.stop_event.is_set():
                self.tick()
                deadline += TICK_S
                if deadline < self.clock():
                    deadline = self.clock()
                self.stop_event.wait(max(0, deadline-self.clock()))
        threading.Thread(target=loop, name='focus-tick', daemon=True).start()
        if CARD_PATH.is_file():
            self.card = subprocess.Popen([str(CARD_PATH)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def close(self):
        self.stop_event.set()
        if self.card and self.card.poll() is None:
            self.card.terminate()
            self.card.wait(timeout=CARD_STOP_TIMEOUT_S)
