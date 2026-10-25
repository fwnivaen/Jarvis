"""Deterministic Mac commands and explicit routines. Never execute model-written shell."""
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from ultra_memory import atomic_json

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / '.local' / 'assistant-state.json'
DESKTOP_APP = ROOT / '.local' / 'Jarvis Desktop.app'
DESKTOP_BINARY = DESKTOP_APP / 'Contents' / 'MacOS' / 'JarvisDesktop'
MAX_TEXT = 2000
MAX_TRIGGER = 80
MAX_SHORTCUTS = 50
MAX_STEPS = 6
MAX_HISTORY = 40
MAX_RECEIPTS = 40
MAX_STATE_BYTES = 500000
COMMAND_TIMEOUT_S = 8
PRIVATE_MODE = 0o600
KEY_PATTERN = re.compile(r'^[a-f0-9]{24,64}$')
APP_FOLDERS = (Path('/Applications'), Path('/System/Applications'), Path('/System/Applications/Utilities'), Path.home() / 'Applications')
APP_ALIASES = {'chrome': 'Google Chrome', 'terminal': 'Terminal', 'settings': 'System Settings', 'chatgpt': 'ChatGPT', 'finder': 'Finder'}
WINDOW_COMMANDS = {'move window left': 'left', 'window left': 'left', 'move window right': 'right',
                   'window right': 'right', 'maximize window': 'maximize', 'centre window': 'center', 'center window': 'center'}
TEACH = re.compile(r'^when i say\s+["“]?(.+?)["”]?\s*,\s*(.+)$', re.I)
BACKGROUND = re.compile(r'^(?:work in (?:the )?background|background task)\s*:\s*(.+)$', re.I | re.S)


class CommandError(ValueError):
    pass


def clean(text):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise CommandError('Enter a command of up to 2,000 characters.')
    return re.sub(r'^(?:(?:hey )?jarvis[, ]+)?(?:please )?', '', text.strip(), flags=re.I).rstrip('.!?').strip()


def installed_apps():
    apps = {}
    for folder in APP_FOLDERS:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.app')):
            apps.setdefault(path.stem.casefold(), path)
    return apps


def action(text):
    text = clean(text)
    key = text.casefold()
    if key in WINDOW_COMMANDS:
        return {'kind': 'window', 'value': WINDOW_COMMANDS[key], 'label': text}
    if key in ('play music', 'pause music', 'resume music'):
        return {'kind': 'music', 'value': 'pause' if key == 'pause music' else 'play', 'label': text}
    match = re.fullmatch(r'(?:search (?:the )?web for|search for)\s+(.+)', text, re.I)
    if match:
        return {'kind': 'url', 'value': 'https://www.google.com/search?q=' + quote_plus(match[1]), 'label': text}
    match = re.fullmatch(r'(?:open|launch)\s+(.+)', text, re.I)
    if match:
        value = match[1].strip()
        if value.startswith(('https://', 'http://')):
            parsed = urlsplit(value)
            if not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
                raise CommandError('Use a complete http or https address without credentials.')
            return {'kind': 'url', 'value': value, 'label': text}
        if value.casefold().endswith('.app'):
            value = value[:-4]
        value = APP_ALIASES.get(value.casefold(), value)
        path = installed_apps().get(value.casefold())
        if path is None:
            raise CommandError('That app is not installed under that name. Use its full app name or open a complete https address.')
        return {'kind': 'app', 'value': str(path), 'label': 'Open ' + path.stem}
    return None


class Assistant:
    def __init__(self, path=STATE_PATH, runner=subprocess.run):
        self.path, self.runner = Path(path), runner
        self.lock = threading.RLock()
        self.state = {'shortcuts': {}, 'history': [], 'receipts': {}}
        self.notice = ''
        try:
            if self.path.is_symlink() or self.path.stat().st_size > MAX_STATE_BYTES:
                raise ValueError
            value = json.loads(self.path.read_text())
            if (not isinstance(value, dict) or not isinstance(value.get('shortcuts'), dict)
                    or not isinstance(value.get('history'), list) or not isinstance(value.get('receipts'), dict)):
                raise ValueError
            if (len(value['shortcuts']) > MAX_SHORTCUTS or len(value['history']) > MAX_HISTORY or len(value['receipts']) > MAX_RECEIPTS
                    or any(not isinstance(k, str) or not 0 < len(k) <= MAX_TRIGGER or not isinstance(v, list) or not 0 < len(v) <= MAX_STEPS or any(not isinstance(c, str) or len(c) > MAX_TEXT for c in v) for k, v in value['shortcuts'].items())
                    or any(not isinstance(r, dict) or not isinstance(r.get('input'), str) or not isinstance(r.get('result'), dict) for r in value['receipts'].values())):
                raise ValueError
            self.state = value
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.notice = 'Saved commands could not be read. Restore the local assistant state before editing routines.'

    def save(self):
        if self.notice or self.path.is_symlink():
            raise CommandError(self.notice or 'The local assistant state must be a regular file.')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(self.path, self.state)
            self.path.chmod(PRIVATE_MODE)
        except (OSError, ValueError):
            self.notice = 'The command journal could not be saved. No further commands will run until storage is available.'
            raise CommandError(self.notice) from None

    def catalog(self):
        with self.lock:
            return {'backend': 'codex-chatgpt', 'desktop_available': DESKTOP_BINARY.is_file(),
                    'voice_available': (ROOT / '.local' / 'Jarvis Voice.app').is_dir(),
                    'notice': self.notice, 'shortcuts': [{'trigger': k, 'commands': v} for k, v in self.state['shortcuts'].items()],
                    'history': self.state['history'], 'examples': ['Open Safari', 'Search the web for macOS shortcuts',
                    'Move window left', 'When I say writing time, open Notes and then open Safari',
                    'Background task: compare the pricing notes']}

    def steps(self, text):
        parts = re.split(r'\s+and then\s+|\s*;\s*', text, flags=re.I)
        if not 0 < len(parts) <= MAX_STEPS:
            raise CommandError('A routine supports up to six commands separated by “and then”.')
        if any(action(part) is None for part in parts):
            raise CommandError('Routines support opening apps or websites, web search, window placement, and Music play/pause.')
        return [clean(part) for part in parts]

    def plan(self, question):
        text = clean(question)
        key = text.casefold()
        teach = TEACH.fullmatch(text)
        if teach:
            trigger = teach[1].strip(' "“”').casefold()
            if not trigger or len(trigger) > MAX_TRIGGER or TEACH.fullmatch(trigger) or BACKGROUND.fullmatch(trigger) or action(trigger):
                raise CommandError('Use a short unique phrase that is not already a built-in command.')
            return {'kind': 'teach', 'trigger': trigger, 'commands': self.steps(teach[2])}
        if key in self.state['shortcuts']:
            # Re-parse on every run: stored state is data, never executable code.
            return {'kind': 'routine', 'trigger': key, 'commands': self.steps(' and then '.join(self.state['shortcuts'][key]))}
        result = action(text)
        return {'kind': 'command', 'commands': [text]} if result else None

    def forget(self, trigger):
        with self.lock:
            if not isinstance(trigger, str) or trigger not in self.state['shortcuts']:
                raise CommandError('That shortcut does not exist.')
            del self.state['shortcuts'][trigger]
            self.save()
            return self.catalog()

    def run_action(self, item, target_pid=None):
        if item['kind'] in ('app', 'url'):
            args = ['/usr/bin/open'] + (['-a', item['value']] if item['kind'] == 'app' else [item['value']])
        else:
            if not DESKTOP_BINARY.is_file():
                raise CommandError('Build the desktop helper with native/build_desktop.sh first.')
            args = [str(DESKTOP_BINARY), '--action', item['kind'], item['value']]
            if target_pid is not None:
                if type(target_pid) is not int or target_pid <= 0:
                    raise CommandError('Invalid target app.')
                args += ['--target', str(target_pid)]
        try:
            result = self.runner(args, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired):
            raise CommandError('The Mac action did not finish. Check the app before trying again.') from None
        if result.returncode:
            raise CommandError('The Mac action was not confirmed. Window controls need Accessibility permission for Jarvis Desktop; Music may need Automation permission.')
        return {'command': item['label'], 'status': 'requested' if item['kind'] in ('app', 'url', 'music') else 'confirmed'}

    def execute(self, question, request_key, target_pid=None):
        if not isinstance(request_key, str) or not KEY_PATTERN.fullmatch(request_key):
            raise CommandError('A unique request key is required.')
        with self.lock:
            if self.notice:
                raise CommandError(self.notice)
            fingerprint = json.dumps([question, target_pid])
            receipt = self.state['receipts'].get(request_key)
            if receipt:
                if receipt['input'] != fingerprint:
                    raise CommandError('This request key belongs to another command.')
                return receipt['result']
            plan = self.plan(question)
            if plan is None:
                return {'matched': False}
            if plan['kind'] == 'teach':
                if plan['trigger'] not in self.state['shortcuts'] and len(self.state['shortcuts']) >= MAX_SHORTCUTS:
                    raise CommandError('The shortcut library is full. Remove one before adding another.')
                self.state['shortcuts'][plan['trigger']] = plan['commands']
                result = {'matched': True, 'answer': 'Saved “' + plan['trigger'] + '”. Say it to run: ' + '; '.join(plan['commands']), 'nodes': [], 'about_notes': False}
            else:
                # Persist an ambiguous receipt BEFORE any side effect. Interrupted runs never replay.
                result = {'matched': True, 'error': True, 'answer': 'This command started but its result was not recorded. Check the app before trying again.', 'nodes': [], 'about_notes': False, 'steps': []}
                self.state['receipts'][request_key] = {'input': fingerprint, 'result': result}
                self.save()
                completed = []
                try:
                    for command in plan['commands']:
                        completed.append(self.run_action(action(command), target_pid))
                    result = {'matched': True, 'answer': '; '.join(step['command'] + (' — requested' if step['status'] == 'requested' else ' — confirmed') for step in completed), 'steps': completed, 'nodes': [], 'about_notes': False}
                except CommandError as error:
                    result = {'matched': True, 'error': True, 'answer': str(error), 'steps': completed, 'nodes': [], 'about_notes': False}
            self.state['history'].insert(0, {'at': time.time(), 'question': question, 'answer': result['answer'], 'ok': not result.get('error', False)})
            del self.state['history'][MAX_HISTORY:]
            self.state['receipts'][request_key] = {'input': fingerprint, 'result': result}
            while len(self.state['receipts']) > MAX_RECEIPTS:
                del self.state['receipts'][next(iter(self.state['receipts']))]
            self.save()
            return result

    def launch(self):
        if not DESKTOP_BINARY.is_file():
            raise CommandError('Build the desktop helper with native/build_desktop.sh first.')
        try:
            result = self.runner(['/usr/bin/open', str(DESKTOP_APP)], capture_output=True, timeout=COMMAND_TIMEOUT_S)
            if result.returncode:
                raise OSError
        except (OSError, subprocess.TimeoutExpired):
            raise CommandError('Jarvis Desktop could not open.') from None
        return {'answer': 'Jarvis Desktop was requested. Use its menu bar icon, or hold Control + Option + Space to talk.', 'nodes': []}
