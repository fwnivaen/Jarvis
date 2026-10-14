"""Opt-in Daniel speaker-to-microphone check; keeps no audio or transcript.

Uses the real speech queue and on-device Mac recognizer. It does not interrupt
an existing microphone session or alter output volume/routing. Playback must
reach the selected microphone for this acoustic check to pass.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import Speaker, SPEECH_VOICE

SERVER = 'http://127.0.0.1:4700'
READY_TIMEOUT_S = 12
AUDIO_TIMEOUT_S = 20
POLL_S = 0.2
REQUEST_TIMEOUT_S = 4
SAMPLE = 'Good evening, sir. The violet compass is ready. Locked on, sir.'
EXPECTED_WORDS = frozenset({'violet', 'compass', 'ready', 'locked'})


def request(action, token=None):
    data = json.dumps({'token': token}).encode()
    req = urllib.request.Request(SERVER+'/voice/'+action, data=data,
                                 headers={'Origin': SERVER, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as response:
        return json.load(response)


def main():
    state = request('start')
    token = state.get('token')
    if not token:
        print(json.dumps({'passed': False, 'reason': state.get('text', 'Microphone unavailable')}))
        return 1
    speaker = Speaker()
    result = {'voice': SPEECH_VOICE, 'microphone_ready': False,
              'sample_detected': False, 'speech_completed': False}
    try:
        deadline = time.monotonic()+READY_TIMEOUT_S
        while time.monotonic() < deadline:
            state = request('poll', token)
            if state['status'] == 'error':
                raise RuntimeError(state.get('text', 'Microphone error'))
            if state['status'] == 'listening':
                result['microphone_ready'] = True
                break
            time.sleep(POLL_S)
        if not result['microphone_ready']:
            raise RuntimeError('Microphone did not become ready')
        speaker(SAMPLE)
        deadline = time.monotonic()+AUDIO_TIMEOUT_S
        while time.monotonic() < deadline:
            state = request('poll', token)
            words = set(state.get('text', '').lower().replace('.', '').replace(',', '').split())
            result['sample_detected'] |= EXPECTED_WORDS <= words
            result['speech_completed'] = not speaker.busy()
            if result['sample_detected'] and result['speech_completed']:
                break
            if state['status'] == 'error':
                raise RuntimeError(state.get('text', 'Microphone error'))
            time.sleep(POLL_S)
        result['passed'] = result['sample_detected'] and result['speech_completed']
    except RuntimeError as error:
        result.update(passed=False, reason=str(error))
    finally:
        request('stop', token)
    print(json.dumps(result))
    return int(not result['passed'])


if __name__ == '__main__':
    sys.exit(main())
