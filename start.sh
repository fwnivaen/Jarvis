#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python3 build.py
printf '%s\n' 'Open http://localhost:4700 in Chrome. Keep this window open; Ctrl+C stops Jarvis.'
exec python3 server.py
