"""Run the full Python suite and all browser-controller regressions locally."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".local/ultra-full-venv/bin/python"
BUNDLED_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", action="store_true", help="Also exercise the downloaded local embedding model")
    args = parser.parse_args()
    python = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
    node = shutil.which("node") or (str(BUNDLED_NODE) if BUNDLED_NODE.is_file() else None)
    if not node:
        parser.error("Node.js is needed for the browser-controller checks.")
    environment = dict(os.environ)
    if args.embeddings:
        environment["ULTRA_EMBEDDINGS_TEST"] = "1"
    result = subprocess.run([python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        cwd=ROOT, env=environment)
    failed = result.returncode != 0
    for path in sorted((ROOT / "tests").glob("*.cjs")):
        result = subprocess.run([node, str(path)], cwd=ROOT)
        failed |= result.returncode != 0
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
