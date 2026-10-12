"""Mac-only speech bridge. Audio stays in the native helper; Python uses stdlib."""
import atexit
import json
import secrets
import subprocess
import tempfile
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent / '.local' / 'Jarvis Voice.app'
SESSION_TOKEN_BYTES = 24
SESSION_LEASE_S = 10
REAPER_INTERVAL_S = 2
STOP_WAIT_S = 3
LOCK = threading.RLock()
SESSION = None


def stop():
    global SESSION
    with LOCK:
        if SESSION is None:
            return
        state = SESSION
        SESSION = None
        folder = Path(state['scratch'].name)
        (folder / 'stop').touch()
        try:
            state['process'].wait(timeout=STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            # The helper also exits when its heartbeat disappears.
            pass
        state['scratch'].cleanup()


def handle(action, token=None):
    global SESSION
    with LOCK:
        if action == 'start':
            if not APP.is_dir():
                return {'status': 'error', 'text': 'The Mac voice helper needs to be built. Run native/build_voice.sh in the Jarvis folder.'}
            if SESSION:
                return {'status': 'error', 'text': 'Another Jarvis tab is using the Mac microphone. Turn its Mic off first.'}
            scratch = tempfile.TemporaryDirectory(prefix='jarvis-voice-')
            folder = Path(scratch.name)
            (folder / 'heartbeat').touch()
            try:
                process = subprocess.Popen(['/usr/bin/open', '-n', '-W', str(APP), '--args', '--session', str(folder)],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                scratch.cleanup()
                return {'status': 'error', 'text': 'The Mac voice helper could not start.'}
            token = secrets.token_hex(SESSION_TOKEN_BYTES)
            SESSION = dict(token=token, scratch=scratch, process=process, touched=time.monotonic())
            return {'token': token, 'status': 'starting'}
        if not SESSION or not isinstance(token, str) or not secrets.compare_digest(token, SESSION['token']):
            return {'status': 'error', 'text': 'The microphone session ended. Click Mic to retry.'}
        if action == 'stop':
            stop()
            return {'status': 'stopped'}
        SESSION['touched'] = time.monotonic()
        folder = Path(SESSION['scratch'].name)
        (folder / 'heartbeat').touch()
        try:
            state = json.loads((folder / 'state.json').read_text())
        except (OSError, ValueError):
            state = {'status': 'starting'}
        if SESSION['process'].poll() is not None and state['status'] != 'error':
            state = {'status': 'error', 'text': 'Mac voice stopped. Click Mic to retry.'}
        return state


def reap():
    while True:
        time.sleep(REAPER_INTERVAL_S)
        with LOCK:
            if SESSION and time.monotonic() - SESSION['touched'] > SESSION_LEASE_S:
                stop()


threading.Thread(target=reap, daemon=True).start()
atexit.register(stop)
