"""Deterministic privacy and accounting checks, without macOS access or speech."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import Focus, PUBLIC_KEYS, LEDGER_KEYS, parse_command, Speaker
from focus_reader import Reader, FRONT_SCRIPT


class Clock:
    value = 0.0
    def __call__(self):
        return self.value


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.bundle = 'com.google.Chrome'
        self.url = 'https://private-work.example/customer/SECRET?token=SECRET#SECRET'
        self.tab_id = 1
        self.queries = []
        def query(script):
            self.queries.append(script)
            if self.bundle is None:
                raise OSError('private diagnostic')
            return self.bundle if script == FRONT_SCRIPT else f'{self.url}\n1\n{self.tab_id}'
        self.reader = Reader(query)
        self.speech = []
        self.path = Path(self.temp.name) / 'ledger.json'
        self.focus = Focus(self.reader, self.clock, self.speech.append, self.path)

    def test_reader_timeout_cannot_arm_or_reuse_a_settling_sample(self):
        self.reader.sample(arm=True, settle=True)
        original_query = self.reader._query
        def timeout(script):
            raise subprocess.TimeoutExpired('private query omitted', 1.2)
        self.reader._query = timeout
        result = self.reader.sample(arm=True, settle=True)
        self.assertFalse(result['known'])
        self.assertFalse(result['target'])
        self.assertIsNone(self.reader._target)
        self.assertEqual(self.reader._ticks, 0)
        self.reader._query = original_query
        self.assertFalse(self.reader.sample(arm=True, settle=True)['locked'])
        self.assertTrue(self.reader.sample(arm=True, settle=True)['locked'])
        self.assert_private()

    def test_eyes_privacy_counting_and_relief(self):
        self.focus.command('start', 600)
        signal = dict(eyes_active=True, present=True, head_down=True, slouched=False)
        self.focus.eyes_update(signal)
        self.focus.eyes_update(signal)
        self.assertEqual(self.focus.drifts, 1)
        self.tick()
        self.assertEqual(self.focus.on_target, 0)
        self.assertEqual(self.focus.drift_time, 1)
        with self.assertRaises(ValueError):
            self.focus.eyes_update(dict(signal, image='forbidden'))
        self.focus.relief()
        self.assertEqual(self.focus.state()['snooze_s'], 180)
        self.focus.eyes_update(dict(signal, head_down=False))
        self.url = 'https://away.example'
        self.tick()
        self.tick()
        self.assertEqual(self.speech, [])
        self.assert_private()

    def test_relief_and_attention_gate_every_native_announcement(self):
        self.focus.relief()
        self.focus.say('Do not interrupt')
        self.clock.value += 179
        self.focus.say('Still quiet')
        self.assertEqual(self.speech, [])
        self.clock.value += 1
        self.focus.say('Allowed after relief')
        self.assertEqual(self.speech, ['Allowed after relief'])
        self.focus.attention()
        self.focus.say('Do not talk over the user')
        self.assertEqual(len(self.speech), 1)
        self.clock.value += 3
        self.focus.say('The user has finished')
        self.assertEqual(len(self.speech), 2)

    def tick(self, seconds=1):
        self.clock.value += seconds
        self.focus.tick()

    def assert_private(self):
        state = self.focus.state()
        self.assertEqual(set(state), PUBLIC_KEYS)
        self.assertTrue(all(type(v) in (bool, int, float) for v in state.values()))
        encoded = json.dumps(state)
        for identity in ('com.google.Chrome', 'private-work', 'SECRET', 'evil.example', 'sha256'):
            self.assertNotIn(identity, encoded)
        self.assertEqual(set(self.reader.sample()), {'known', 'home', 'target', 'locked'})

    def test_reader_fresh_host_only_and_home(self):
        self.focus.command('start', 100)
        self.url = 'https://private-work.example/different/path?other=secret'
        self.tick()
        self.assertFalse(self.focus.state()['drifting'])
        self.assertEqual(self.queries.count(FRONT_SCRIPT), 4)
        self.url = 'https://evil.example/'
        self.tick()
        self.assertEqual(len(self.speech), 0)
        self.tick()
        self.assertEqual(len(self.speech), 1)
        self.assert_private()
        self.url = 'http://localhost:4700/?mute=1'
        self.tick(40)
        self.assertTrue(self.focus.state()['home'])
        self.assertEqual(len(self.speech), 1)
        self.focus.command('excuse')
        self.assertEqual(self.focus.state()['drifts'], 0)
        self.assertEqual(self.focus.state()['drift_s'], 0)
        self.url = 'https://evil.example/'
        self.tick(40)
        self.assertEqual(len(self.speech), 1)
        self.url = 'https://private-work.example/back'
        self.tick()
        self.assertFalse(self.focus.state()['excused'])

    def test_reload_is_read_only_and_privacy_all_states(self):
        self.url = 'http://127.0.0.1:4700/'
        self.focus.command('start', 100)
        self.assertTrue(self.focus.state()['armed'])
        self.assert_private()
        self.tick(10)
        self.assertEqual(self.focus.state()['remaining_s'], 100)
        self.url = 'https://private-work.example/task'
        self.tick()
        for _ in range(5):
            self.assert_private()  # Reloads/polls cannot advance or reset a session.
        self.assertEqual(self.focus.state()['remaining_s'], 100)
        self.tick()
        self.bundle = 'org.secret.OtherApp'
        self.tick()
        self.tick()
        for command, seconds in [('pause', None), ('resume', None), ('snooze', 15), ('nag', 30), ('excuse', None), ('extend', 60), ('end', None)]:
            self.focus.command(command, seconds)
            self.assert_private()
        ledger = json.loads(self.path.read_text())
        self.assertEqual(set(ledger), set(LEDGER_KEYS))
        self.assertTrue(all(type(v) in (int, float) for v in ledger.values()))
        self.assertIsNone(self.reader._target)

    def test_pause_nag_snooze_tiers_return_and_abort(self):
        self.focus.command('start', 500)
        self.focus.command('nag', 3)
        self.bundle = 'org.other.app'
        self.tick()
        self.tick()
        self.assertEqual(self.focus.state()['tier'], 1)
        self.focus.command('snooze', 15)
        self.tick(14)
        self.assertEqual(len(self.speech), 1)
        self.tick()
        self.assertEqual(self.focus.state()['tier'], 2)
        self.tick(3)
        self.assertEqual(self.focus.state()['tier'], 3)
        self.assertEqual(self.focus.state()['drifts'], 1)
        self.focus.command('pause')
        before = self.focus.state()['remaining_s']
        self.tick(50)
        self.assertEqual(self.focus.state()['remaining_s'], before)
        self.focus.command('resume')
        self.bundle = 'com.google.Chrome'
        self.tick()
        self.assertFalse(self.focus.state()['drifting'])
        self.focus.command('abort')
        self.assertTrue(self.focus.state()['aborted'])
        self.assertIn('Aborted', self.speech[-1])
        self.assertEqual(self.focus.state()['streak'], 0)

    def test_unavailable_does_not_claim_focus(self):
        self.focus.command('start', 100)
        self.bundle = None
        self.tick(50)
        self.assertFalse(self.focus.state()['known'])
        self.assertEqual(self.focus.state()['elapsed_s'], 0)
        self.assertEqual(self.speech, [])

    def test_clean_streak_persisted_early_end_does_not_earn_it(self):
        self.focus.command('start', 10)
        self.tick(10)
        self.assertTrue(self.focus.state()['completed'])
        self.assertEqual(self.focus.state()['streak'], 1)
        restored = Focus(self.reader, self.clock, self.speech.append, self.path)
        self.assertEqual(restored.state()['streak'], 1)
        restored.command('start', 100)
        restored.command('end')
        self.assertEqual(restored.state()['streak'], 0)
        self.assertIn('minutes on target out of', self.speech[-1])

    def test_grace_refunded_and_bad_values(self):
        self.focus.command('start', 20)
        self.bundle = 'other'
        self.tick()
        self.bundle = 'com.google.Chrome'
        self.tick(0.5)
        self.assertEqual(self.focus.state()['drifts'], 0)
        self.assertEqual(self.focus.state()['drift_s'], 0)
        for value in (float('nan'), float('inf'), -1, True, '30'):
            with self.assertRaises(ValueError):
                self.focus.command('extend', value)

    def test_http_state_privacy_origin_and_reload(self):
        from unittest.mock import patch
        from test_offline import request
        import server
        with patch.object(server, 'FOCUS', self.focus):
            denied, _, _ = request('/focus', 'POST', {'action': 'start'})
            self.assertEqual(denied, 403)
            status, _, body = request('/focus', 'POST', {'question': 'thirty minutes on this'},
                                     {'Origin': 'http://127.0.0.1:4700'})
            self.assertEqual(status, 200)
            self.assertEqual(set(json.loads(body)['state']), PUBLIC_KEYS)
            self.tick(2)
            for _ in range(2):
                status, _, body = request('/focus')
                state = json.loads(body)
                self.assertEqual(status, 200)
                self.assertEqual(set(state), PUBLIC_KEYS)
                self.assertTrue(all(type(v) in (bool, int, float) for v in state.values()))
                self.assertEqual(state['remaining_s'], 1798)
            self.assert_private()

    def test_internal_browser_pages_are_drift_not_permission_failure(self):
        self.focus.command('start', 30)
        for url in ('chrome://newtab/', 'about:blank', 'file:///private/test.html'):
            self.url = url
            self.tick()
            self.tick()
            self.assertTrue(self.focus.state()['known'])
            self.assertTrue(self.focus.state()['drifting'])

    def test_deferred_two_ticks_reset_and_audible_lock(self):
        self.url = 'http://localhost:4700/'
        message = self.focus.command('start', 100)
        self.assertEqual(message, "Go to what you're working on and I'll lock on there. And what are we focusing on?")
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.url = 'https://work.example/'
        self.tick()
        self.url = 'http://localhost:4700/'
        self.tick()
        self.url = 'https://work.example/'
        self.tick()
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.tick()
        self.assertFalse(self.focus.state()['lock_deferred'])
        self.assertEqual(self.speech, ['Locked on, sir.'])
        self.assertEqual(self.focus.set_intent('finish the quarterly budget and reconcile all the vendor invoices'), 'Noted, sir.')
        self.url = 'https://elsewhere.example/'
        self.tick()
        self.tick()
        self.assertIn('quarterly budget', self.speech[-1])
        report = self.focus.command('end')
        self.assertIn('quarterly budget', report)
        self.assertNotIn('vendor invoices', report)

    def test_different_tab_same_host_does_not_settle_or_match(self):
        self.url = 'http://localhost:4700/'
        self.focus.command('start', 100)
        self.url = 'https://work.example/'
        self.tick()
        self.tab_id = 2
        self.tick()
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.tick()
        self.tab_id = 3
        self.tick()
        self.tick()
        self.assertTrue(self.focus.state()['drifting'])

    def test_viewer_click_always_defers_and_intent_is_single_answer(self):
        self.focus.command('start', 100, defer_lock=True)
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.assertIsNone(self.reader._target)
        self.tick()
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.tick()
        self.assertFalse(self.focus.state()['lock_deferred'])
        self.focus.set_intent('x' * 3000)
        self.assertLess(len(self.focus.intent_label()), 70)
        with self.assertRaises(ValueError):
            self.focus.set_intent('second answer')
        self.assert_private()

    def test_window_mismatch_cannot_arm(self):
        def mismatch(script):
            if script == FRONT_SCRIPT:
                return 'com.google.Chrome'
            self.assertIn('AXFocusedWindow', script)
            self.assertNotIn('every window', script)
            raise OSError('Focused window does not match browser window')
        reader = Reader(mismatch)
        for _ in range(3):
            self.assertFalse(reader.sample(arm=True, settle=True)['locked'])

    def test_failed_click_and_failed_tick_restart_settling(self):
        self.bundle = None
        self.focus.command('start', 100)
        self.bundle = 'com.google.Chrome'
        self.tick()
        self.bundle = None
        self.tick()
        self.bundle = 'com.google.Chrome'
        self.tick()
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.tick()
        self.assertFalse(self.focus.state()['lock_deferred'])

    def test_home_timeout_is_app_only_and_does_not_read_background(self):
        self.url = 'http://localhost:4700/'
        self.focus.command('start', 100)
        self.tick(44)
        self.assertTrue(self.focus.state()['lock_deferred'])
        self.queries.clear()
        self.tick()
        self.assertTrue(self.focus.state()['app_only'])
        self.assertEqual(self.queries, [FRONT_SCRIPT, FRONT_SCRIPT])
        self.url = 'https://any-tab.example/'
        self.tick()
        self.assertFalse(self.focus.state()['drifting'])

    def test_retarget_phrases(self):
        for text in ('lock on this tab', 'lock this tab', 'keep me in this tab',
                     'this is the tab', 'stay on this tab',
                     "okay, I'm gonna need you to keep me in this tab."):
            self.assertEqual(parse_command(text), ('retarget', None))
        self.assertIsNone(parse_command('lock my screen'))

    def test_retarget_work_refunds_only_current_drift(self):
        self.focus.command('start', 100)
        self.focus.set_intent('write report')
        self.tab_id = 2
        self.tick(); self.tick()
        elapsed = self.focus.elapsed
        spoken = list(self.speech)
        self.assertEqual(self.focus.command('retarget'), 'Locked on, sir.')
        self.assertEqual(self.speech, spoken)  # HTTP layer owns the one confirmation.
        self.assertEqual(self.focus.drifts, 0)
        self.assertEqual(self.focus.drift_time, 0)
        self.assertEqual(self.focus.elapsed, elapsed)
        self.assertEqual(self.focus.intent, 'write report')
        self.tick(); self.tick()
        self.assertFalse(self.focus.state()['drifting'])

    def test_retarget_home_rearms_and_preserves_pause(self):
        self.focus.command('start', 100)
        self.focus.command('pause')
        self.url = 'http://localhost:4700/'
        self.assertEqual(self.focus.command('retarget'), "Go to it, sir — I'll lock on where you land.")
        self.assertTrue(self.focus.armed)
        self.assertTrue(self.focus.paused)
        self.focus.command('resume')
        self.tab_id = 2
        self.url = 'https://work.example/'
        self.tick(); self.tick()
        self.assertFalse(self.focus.armed)
        self.assertEqual(self.speech, ['Locked on, sir.'])

    def test_retarget_card_and_own_process_read_browser_front_window(self):
        for from_card, bundle in ((True, 'com.apple.finder'), (False, 'JarvisFocusCard')):
            self.bundle = 'com.google.Chrome'
            self.focus.command('start', 100)
            self.bundle = bundle
            self.tab_id += 1
            self.queries.clear()
            self.assertEqual(self.focus.command('retarget', from_card=from_card), 'Locked on, sir.')
            browser_script = self.queries[-1]
            self.assertIn('front window', browser_script)
            self.assertNotIn('AXFocusedWindow', browser_script)
            self.assertEqual(self.focus.reader._target[0], 'com.google.Chrome')
            self.focus.command('abort')

    def test_retarget_app_and_failure_preserves_target(self):
        self.focus.command('start', 100)
        self.bundle = 'com.apple.TextEdit'
        self.assertEqual(self.focus.command('retarget'), 'Locked on, sir.')
        target = self.focus.reader._target
        self.assertEqual(target, ('com.apple.TextEdit', None))
        self.bundle = None
        with self.assertRaises(ValueError):
            self.focus.command('retarget')
        self.assertEqual(self.focus.reader._target, target)

    def test_native_speech_pins_daniel(self):
        from unittest.mock import patch, MagicMock
        with patch('focus.subprocess.Popen', return_value=MagicMock()) as launch:
            speaker = Speaker()
            speaker('Locked on, sir.')
            speaker.pending.join()
            self.assertEqual(launch.call_args.args[0],
                             ['/usr/bin/say', '-v', 'Daniel', 'Locked on, sir.'])

    def test_transient_unique_label_never_persisted(self):
        import uuid
        sentinel = 'drift-' + uuid.uuid4().hex + '.example'
        root = Path(__file__).resolve().parents[1]
        notes_before = {str(p): p.read_bytes() for p in (root / 'notes').rglob('*') if p.is_file()}
        self.focus.command('start', 100)
        self.focus.set_intent('the thumbnail sprint')
        self.url = 'https://' + sentinel + '/secret?private=yes'
        self.tick(); self.tick()
        self.assertIn(sentinel, self.speech[-1])
        self.assertIn('the thumbnail sprint', self.speech[-1])
        self.assertNotIn(sentinel, repr(self.focus.state()))
        # Inspect private engine fields too, excluding injected test fixtures/speech sink.
        fields = {k: v for k, v in vars(self.focus).items() if k not in ('reader', 'speak', 'clock')}
        self.assertNotIn(sentinel, repr(fields))
        self.assertNotIn(sentinel, repr({k: v for k, v in vars(self.reader).items() if k != '_query'}))
        report = self.focus.command('end')
        self.assertNotIn(sentinel, report)
        self.assertNotIn(sentinel, self.path.read_text())
        self.assertNotIn(sentinel, repr(self.focus.state()))
        notes_after = {str(p): p.read_bytes() for p in (root / 'notes').rglob('*') if p.is_file()}
        self.assertEqual(notes_before, notes_after)
        for path in root.rglob('*'):
            if path.is_file() and (path.suffix in ('.json', '.jsonl', '.log', '.md')):
                self.assertNotIn(sentinel.encode(), path.read_bytes(), str(path))

    def test_named_browser_and_display_name_callouts(self):
        for url, bundle, expected in (
            ('https://www.instagram.com/reels/private', 'com.google.Chrome', 'Instagram'),
            ('https://www.example.com/private?q=hidden', 'com.google.Chrome', 'example.com'),
            ('', 'com.tinyspeck.slackmacgap\nSlack', 'Slack')):
            with self.subTest(expected=expected):
                self.bundle = 'com.google.Chrome'
                self.url = 'https://work.example/'
                self.focus.command('start', 100)
                self.bundle, self.url = bundle, url
                self.tick(); self.tick()
                self.assertEqual(self.speech[-1], f'{expected} can wait.')
                self.focus.command('end')

    def test_naming_switch_home_and_current_tick(self):
        from unittest.mock import patch
        self.focus.command('start', 200)
        self.url = 'https://instagram.com/'
        self.tick()
        self.url = 'https://youtube.com/'
        self.tick()
        self.assertEqual(self.speech[-1], 'YouTube can wait.')
        self.url = 'http://localhost:4700/'
        self.assertEqual(self.reader.sample(naming=True)['label'], '')
        self.tick(30)
        self.assertEqual(len(self.speech), 1)
        self.url = 'https://instagram.com/'
        with patch('focus.NAME_DISTRACTIONS', False):
            self.tick(30)
        self.assertNotIn('Instagram', self.speech[-1])

    def test_pools_four_lines_and_drill_command(self):
        from focus import POOLS, NAMED_POOLS, DRILL_POOLS
        for pools in (POOLS, NAMED_POOLS, DRILL_POOLS):
            self.assertTrue(all(len(set(pool)) == 4 for pool in pools))
        self.focus.command('start', 500)
        self.assertEqual(parse_command('drill sergeant mode'), ('drill', None))
        self.focus.command('drill')
        self.url = 'https://reddit.com/'
        self.tick(); self.tick()
        self.assertIn('Reddit', self.speech[-1])
        self.assertIn('Execute', self.speech[-1])
        self.focus.command('normal')
        self.focus.command('nag', 3)
        for _ in range(6):
            self.tick(3)
        self.assertEqual(len(set(self.speech[-4:])), 4)

    def test_voice_grammar(self):
        for text, expected in [
            ('thirty minutes on this', ('start', 1800)),
            ('Jarvis, call me out every thirty seconds', ('nag', 30)),
            ('give me fifteen seconds', ('snooze', 15)),
            ("it's okay, I'm doing research", ('excuse', None)),
            ('extend by five minutes', ('extend', 300)),
            ('twenty five minutes on this', ('start', 1500)),
            ('pause', ('pause', None)), ('resume', ('resume', None)),
            ('abort', ('abort', None)), ('end the session', ('end', None))]:
            self.assertEqual(parse_command(text), expected, text)
        self.assertIsNone(parse_command('What does menu pricing say?'))


if __name__ == '__main__':
    unittest.main()

class InstrumentTests(unittest.TestCase):
    setUp = FocusTests.setUp
    tick = FocusTests.tick
    def test_record_whitelist_and_rejection(self):
        from focus import RECORD_KEYS
        self.focus.command('start', 60)
        self.focus.intent = 'SECRET identity'
        self.focus.ledger['untrusted'] = 'SECRET'
        self.tick(10)
        self.focus.command('end')
        path = self.path.with_name('ledger-sessions.json')
        before = path.read_bytes()
        record = json.loads(before)[0]
        self.assertEqual(set(record), RECORD_KEYS)
        self.assertNotIn('SECRET', before.decode())
        self.assertAlmostEqual(record['active_minutes'], 10/60)
        self.assertTrue(record['completed'])
        for key in ('url', 'host', 'hash', 'bundle', 'intent', 'app', 'title', 'arbitrary'):
            with self.assertRaises(ValueError):
                self.focus.write_record(dict(record, **{key:'SECRET'}))
            self.assertEqual(path.read_bytes(), before)
        for key in RECORD_KEYS - {'timestamp', 'completed'}:
            for bad in ('SECRET', {'url':'SECRET'}, float('nan'), float('inf'), True):
                with self.assertRaises(ValueError):
                    self.focus.write_record(dict(record, **{key:bad}))
        self.assertEqual(path.read_bytes(), before)

    def test_diag_live_read_does_not_lock_or_settle(self):
        self.focus.command('start', 60, defer_lock=True)
        before = (self.reader._target, self.reader._candidate, self.reader._ticks)
        diag = self.focus.diagnostic()
        self.assertEqual(before, (self.reader._target, self.reader._candidate, self.reader._ticks))
        self.assertTrue(diag['front_readable'])
        self.assertTrue(diag['hash_present'])
        self.assertFalse(diag['tick_thread_alive'])
        self.assertEqual(set(diag), {'front_readable','is_browser','tab_status','front_is_jarvis',
            'hash_present','app_on_target','tab_on_target','settle_ticks','app_target','tab_target',
            'lock_deferred','session_on','tick_thread_alive','tick_status'})
        self.bundle = None
        self.assertFalse(self.focus.diagnostic()['front_readable'])
        self.assertNotIn('SECRET', json.dumps(diag))
        self.clock.value += 10
        self.assertEqual(self.focus.diagnostic()['tick_status'], 'stalled')

    def test_diag_survives_locked_tick_and_tab_failure(self):
        import threading
        self.focus.command('start', 60)
        original = self.reader._query
        def broken_tab(script):
            if script != FRONT_SCRIPT:
                raise OSError('SECRET')
            return original(script)
        self.reader._query = broken_tab
        held, release = threading.Event(), threading.Event()
        def hold():
            with self.focus.lock:
                held.set()
                release.wait(2)
        thread = threading.Thread(target=hold)
        thread.start()
        held.wait(1)
        try:
            diag = self.focus.diagnostic()
            self.assertTrue(thread.is_alive())
            self.assertTrue(diag['app_on_target'])
            self.assertEqual(diag['tab_status'], 'unavailable')
            self.assertFalse(diag['tab_on_target'])
        finally:
            release.set()
            thread.join()

    def test_record_abort_and_poisoned_history(self):
        self.focus.command('start', 60)
        self.focus.command('abort')
        path = self.path.with_name('ledger-sessions.json')
        record = json.loads(path.read_text())[0]
        self.assertFalse(record['completed'])
        poisoned = dict(record, on_target_minutes={'url':'SECRET'})
        path.write_text(json.dumps([poisoned]))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.focus.write_record(record)
        self.assertEqual(before, path.read_bytes())

    def test_restart_restores_frozen_counters_and_rearms_without_identity(self):
        from focus import SNAPSHOT_KEYS
        self.focus.command('start', 600)
        self.focus.set_intent('SECRET private intention')
        self.focus.command('drill')
        self.tick(12)
        self.url = 'https://elsewhere.example/SECRET'
        self.tick()
        self.tick()
        before = self.focus.state()
        snapshot = self.path.with_name('ledger-active.json')
        raw = snapshot.read_text()
        values = json.loads(raw)
        self.assertEqual(set(values), SNAPSHOT_KEYS)
        self.assertTrue(all(type(v) in (bool, int, float) for v in values.values()))
        for forbidden in ('SECRET', 'elsewhere', 'private-work', 'com.google', 'intent', 'hash', 'url', 'host', 'title'):
            self.assertNotIn(forbidden, raw)
        self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
        self.clock.value += 7200  # Offline time must not advance the saved timer.
        restored_reader = Reader(self.reader._query)
        restored = Focus(restored_reader, self.clock, self.speech.append, self.path)
        self.assertTrue(restored.active)
        self.assertTrue(restored.armed)
        self.assertTrue(restored.drill)
        self.assertFalse(restored.known)
        self.assertEqual(restored.intent, '')
        self.assertIsNone(restored_reader._target)
        for field in ('planned_s', 'elapsed_s', 'on_target_s', 'drift_s', 'drifts', 'remaining_s'):
            self.assertEqual(restored.state()[field], before[field])
        self.clock.value += 1
        restored.tick()
        self.assertTrue(restored.armed)
        self.clock.value += 1
        restored.tick()
        self.assertFalse(restored.armed)
        self.assertEqual(restored.elapsed, before['elapsed_s'])
        self.clock.value += 1
        restored.tick()
        self.assertEqual(restored.elapsed, before['elapsed_s'] + 1)
        self.assertEqual(set(restored.state()), PUBLIC_KEYS)

    def test_restart_preserves_pause_relief_and_finishing_tombstones(self):
        self.focus.command('start', 600)
        self.tick(10)
        self.focus.command('nag', 12)
        self.focus.command('snooze', 30)
        self.focus.relief()
        self.focus.command('pause')
        self.focus.muted = True
        self.focus.close()
        self.clock.value += 1000
        restored = Focus(Reader(self.reader._query), self.clock, self.speech.append, self.path)
        self.assertTrue(restored.paused)
        self.assertTrue(restored.muted)
        self.assertEqual(restored.nag, 12)
        self.assertEqual(restored.state()['snooze_s'], 180)
        self.clock.value += 20
        restored.tick()
        self.assertEqual(restored.elapsed, 10)
        restored.command('resume')
        restored.command('end')
        finished = json.loads(restored.snapshot_path.read_text())
        self.assertFalse(finished['active'])
        again = Focus(Reader(self.reader._query), self.clock, self.speech.append, self.path)
        self.assertFalse(again.active)
        self.assertEqual(again.ledger['sessions'], 1)
        self.assertEqual(len(json.loads(self.path.with_name('ledger-sessions.json').read_text())), 1)

    def test_restart_snapshot_rejects_poisoning_and_nonfinite_state(self):
        from focus import SNAPSHOT_NUMBER_KEYS
        self.focus.command('start', 600)
        snapshot = self.focus.snapshot_path
        valid = json.loads(snapshot.read_text())
        bad_values = [dict(valid, url='SECRET'), dict(valid, active=1), dict(valid, version=2),
                      dict(valid, drifts=1.5), dict(valid, elapsed_s=601),
                      dict(valid, on_target_s=1), dict(valid, relief_s=181)]
        for field in SNAPSHOT_NUMBER_KEYS:
            for value in ('SECRET', {'url': 'SECRET'}, float('nan'), float('inf'), True, -1):
                bad_values.append(dict(valid, **{field: value}))
        for values in bad_values:
            with self.subTest(values=values):
                snapshot.write_text(json.dumps(values))
                before = snapshot.read_bytes()
                restored = Focus(Reader(self.reader._query), self.clock, self.speech.append, self.path)
                self.assertFalse(restored.active)
                self.assertFalse(restored.state()['ledger_ok'])
                self.assertIsNone(restored.reader._target)
                self.assertEqual(set(restored.state()), PUBLIC_KEYS)
                self.assertEqual(snapshot.read_bytes(), before)
