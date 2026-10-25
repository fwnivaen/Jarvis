# Project rules

- Never print, log, commit, or move config.json or any API key. It stays gitignored and unreachable from the browser.
- Never edit .gitignore to un-ignore config.json or viewer/graph-data.js.
- Never ask me to paste an API key into chat; I type keys into config.json myself.
- After finishing and verifying each task, commit with a clear message like "Prompt 03: camera dive to source" and push to origin main.
- Once preflight.py exists, run it before saying any change is done, and paste its summary line.
- Run python3 preflight.py before saying any change is done; use --quick only for UI-only changes.
- Server code uses the Python standard library unless I approve otherwise (a native helper for the desktop card in Part Two is approved). The viewer has no npm build step.
- Every tunable number is a named constant at the top of its file.

## Desktop acceptance checks

Focus has been removed at the user's request. Do not restore its timer, foreground monitoring, tool endpoints, card, or probe. Verify `/focus` returns 404 and test the Mac assistant dashboard in a visible browser. Run full `python3 preflight.py` and report its summary. Native microphone and Accessibility permissions need user acceptance; report missing permissions honestly.
