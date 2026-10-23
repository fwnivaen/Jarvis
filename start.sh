#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .local/JarvisFocusCard ] || [ native/FocusCard.swift -nt .local/JarvisFocusCard ]; then
    native/build_focus.sh
fi
JARVIS_PYTHON=python3
if [ -x .local/ultra-full-venv/bin/python ] && python3 -c 'from ultra import Settings; raise SystemExit(not Settings.read()[0].enabled)'; then
    JARVIS_PYTHON=.local/ultra-full-venv/bin/python
fi
"$JARVIS_PYTHON" build.py
printf '%s\n' 'Open http://localhost:4700 in Chrome. Keep this window open; Ctrl+C stops Jarvis.'
exec "$JARVIS_PYTHON" server.py
