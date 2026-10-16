# Project rules

- Never print, log, commit, or move config.json or any API key. It stays gitignored and unreachable from the browser.
- Never edit .gitignore to un-ignore config.json or viewer/graph-data.js.
- Never ask me to paste an API key into chat; I type keys into config.json myself.
- After finishing and verifying each task, commit with a clear message like "Prompt 03: camera dive to source" and push to origin main.
- Once preflight.py exists, run it before saying any change is done, and paste its summary line.
- Run python3 preflight.py before saying any change is done; use --quick only for UI-only changes.
- Server code uses the Python standard library unless I approve otherwise (a native helper for the desktop card in Part Two is approved). The viewer has no npm build step.
- Every tunable number is a named constant at the top of its file.

## Field debugging law

Before changing code for a reported failure, fetch `/focus/diag` from the RUNNING
server, read `ledger-focus-sessions.json` (and legacy aggregate totals), count
browser windows, and inspect the host of the assistant-controlled tab. Record
missing instruments as missing; a fresh Python process is not evidence about the
long-lived server. If multiple fixes change nothing, stop patching and reproduce
the user's exact flow with `?focusdebug=1` and diagnostics visible: question the
input and selected window/tab first. Do not log identities into diagnostics.

Run `?focusprobe=1` in a visible browser at an asserted 1440×900 viewport, read its
full title (per-case PASS/FAIL), and run full `python3 preflight.py`. Report both
summary lines. A hidden or wrong-size probe is a failure, never a timing pass.
