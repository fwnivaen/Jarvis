"""Opt-in physical Mac test: activates Chrome, opens disposable local tabs, speaks.

Run only when foreground browser control and audible output are wanted. Uses the
real server, reader, timer and speaker; adds one real session to aggregate totals.
"""
import json
import subprocess
import time
import urllib.request

SERVER = 'http://127.0.0.1:4700'
WORK_URL = SERVER + '/focus-verification-work'
DRIFT_URL = 'http://localhost:4700/focus-verification-drift'
DURATION_S = 60
CALLOUT_LIMIT_S = 3
POLL_S = 0.05
SETTLE_S = 2
WAIT_S = 5
SCRIPT_TIMEOUT_S = 10
HTTP_TIMEOUT_S = 3
PRECISION = 3


def script(source):
    result = subprocess.run(['/usr/bin/osascript', '-e', source], capture_output=True,
                            text=True, timeout=SCRIPT_TIMEOUT_S)
    if result.returncode:
        raise RuntimeError('Chrome automation failed; check Automation permission.')
    return result.stdout.strip()


def request(body=None):
    headers = {'Content-Type': 'application/json', 'Origin': SERVER}
    payload = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(SERVER+'/focus', data=payload,
                                                      headers=headers), timeout=HTTP_TIMEOUT_S) as response:
        return json.load(response)


def wait_for(predicate, timeout=WAIT_S):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        state = request()
        if predicate(state):
            return state
        time.sleep(POLL_S)
    raise RuntimeError('Expected focus transition was not observed.')


def main():
    if request()['active']:
        raise RuntimeError('An existing session is running; finish it before this test.')
    window = None
    started = False
    try:
        window = script(f'''tell application "Google Chrome"
activate
set testWindow to make new window
set URL of active tab of testWindow to "{WORK_URL}"
make new tab at end of tabs of testWindow with properties {{URL:"{DRIFT_URL}"}}
set active tab index of testWindow to 1
return id of testWindow
end tell''')
        if not window.isdecimal():
            raise RuntimeError('Could not identify the disposable test window.')
        time.sleep(SETTLE_S)
        state = request({'action': 'start', 'seconds': DURATION_S})['state']
        started = True
        if state['armed'] or not state['known']:
            raise RuntimeError('The real activity reader could not lock the work tab.')
        time.sleep(SETTLE_S)
        before = time.monotonic()
        script(f'tell application "Google Chrome" to set active tab index of window id {window} to 2')
        drift = wait_for(lambda s: s['drifting'] and s['drifts'] == 1 and s['speaking'], CALLOUT_LIMIT_S)
        latency = time.monotonic()-before
        if latency > CALLOUT_LIMIT_S:
            raise RuntimeError('Callout exceeded the three-second acceptance limit.')
        print(json.dumps({'drift_recorded': drift['drifts'], 'callout_process_started_s': round(latency, PRECISION)}), flush=True)
        script(f'tell application "Google Chrome" to set active tab index of window id {window} to 1')
        wait_for(lambda s: not s['drifting'] and s['known'])
        script(f'tell application "Google Chrome" to set URL of active tab of window id {window} to "{SERVER}/"')
        home = wait_for(lambda s: s['home'] and not s['drifting'])
        script(f'tell application "Google Chrome" to reload active tab of window id {window}')
        time.sleep(SETTLE_S)
        rejoined = request()
        if not rejoined['active'] or rejoined['remaining_s'] > home['remaining_s'] or rejoined['drifts'] != 1:
            raise RuntimeError('Reload failed to preserve the session.')
        result = request({'question': 'end the session'})
        if result['state']['active'] or result['state']['drifts'] != 1 or not result['state']['speaking']:
            raise RuntimeError('The final report did not retain the recorded drift or start speech.')
        started = False
        print(json.dumps({'returned_to_target': True, 'home_exempt': True, 'reload_rejoined': True,
                          'final_drifts': result['state']['drifts'], 'report_speech_started': True}), flush=True)
        # Keep the final report visible briefly, then close only our disposable window.
        wait_for(lambda s: not s['speaking'], SCRIPT_TIMEOUT_S)
    finally:
        if started:
            request({'action': 'abort'})
        if window is not None and window.isdecimal():
            script(f'tell application "Google Chrome" to close window id {window}')


if __name__ == '__main__':
    main()
