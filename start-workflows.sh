#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .local/ultra-full-venv/bin/python ]; then
    printf '%s\n' 'Run python3 tools/setup_ultra.py --no-model first.'
    exit 1
fi
exec .local/ultra-full-venv/bin/python tools/run_workflows.py
