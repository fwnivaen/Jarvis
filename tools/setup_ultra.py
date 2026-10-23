"""Install verified Ultra dependencies in a project-local Python 3.11+ venv."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".local" / "ultra-full-venv"
BUNDLED = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
MIN_PYTHON = (3, 11)


def supported(executable):
    try:
        return subprocess.run([str(executable), "-c", "import sys; raise SystemExit(sys.version_info[:2] < (3,11))"],
            capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", help="Path to a Python 3.11+ interpreter")
    parser.add_argument("--no-model", action="store_true", help="Skip the public local embedding model download")
    args = parser.parse_args()
    candidates = [args.python] if args.python else [sys.executable, shutil.which("python3.13"),
        shutil.which("python3.12"), shutil.which("python3.11"), str(BUNDLED)]
    executable = next((p for p in candidates if p and supported(p)), None)
    if not executable:
        parser.error("Install Python 3.11 or newer, then rerun with --python /path/to/python3.")
    VENV.parent.mkdir(exist_ok=True, mode=0o700)
    if not (VENV / "bin/python").exists():
        subprocess.run([str(executable), "-m", "venv", str(VENV)], check=True)
    python = str(VENV / "bin/python")
    if not supported(python):
        parser.error("The existing Ultra virtual environment needs Python 3.11+. Recreate only that environment.")
    subprocess.run([python, "-m", "pip", "install", "-r", str(ROOT / "requirements-ultra.txt")], check=True)
    if not args.no_model:
        model_dir = ROOT / ".local" / "ultra-models"
        model_dir.mkdir(exist_ok=True, mode=0o700)
        subprocess.run([python, "-c", "from fastembed import TextEmbedding; import sys; "
            "m=TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir=sys.argv[1],threads=2); "
            "print('Local embedding dimensions:',len(next(iter(m.embed(['verification'])))))", str(model_dir)], check=True)
    print("Ultra is ready. Run .local/ultra-full-venv/bin/python server.py")


if __name__ == "__main__":
    main()
