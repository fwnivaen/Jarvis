"""Launch the integrated workflows with private local flags, without editing ultra.json."""
import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / '.local' / 'workflow-settings.json'
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adaptive-routing', action='store_true',
                        help='Opt in to the evaluated adaptive profiles; see docs/routing-checklist.md.')
    args = parser.parse_args()
    import server
    import ultra
    try:
        import langgraph.checkpoint.sqlite  # noqa: F401
    except ImportError:
        raise SystemExit('Run python3 tools/setup_ultra.py --no-model, then ./start-workflows.sh')
    LOCAL_CONFIG.parent.mkdir(exist_ok=True, mode=0o700)
    settings = replace(ultra.Settings.read()[0], enabled=True, workflows_enabled=True, tools_enabled=True)
    if args.adaptive_routing:
        settings = replace(settings, adaptive_routing_enabled=True)
    if LOCAL_CONFIG.is_symlink():
        raise SystemExit('Use a regular private workflow settings file.')
    fd = os.open(LOCAL_CONFIG, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(settings.__dict__, handle, indent=2)
    server.ULTRA_CONFIG_PATH = LOCAL_CONFIG
    server.main()


if __name__ == '__main__':
    main()
