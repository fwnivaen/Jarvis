"""Check tracked source hygiene and local Markdown links without reading secrets."""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = frozenset({"config.json", "graph-data.js", ".env", ".DS_Store"})
PRIVATE_PARTS = frozenset({".local", ".venv", "venv", "__pycache__", "node_modules"})
PRIVATE_SUFFIXES = frozenset({".key", ".pem", ".p12", ".pyc", ".log"})
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^\n)]+)\)")
LOCAL_HOME = re.compile(r"/Users/[^\s/]+/|/home/[^\s/]+/")
SECRET_PATTERNS = {
    "OpenAI token": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b"),
    "OpenRouter token": re.compile(rb"\bsk-or-v1-[A-Za-z0-9]{40,}\b"),
    "GitHub token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS key ID": re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    failures = []
    file_count = link_count = 0
    for name in filter(None, names):
        relative = Path(name)
        if (relative.name in PRIVATE_NAMES or relative.name.startswith(".env.")
                or PRIVATE_PARTS.intersection(relative.parts)
                or relative.suffix in PRIVATE_SUFFIXES
                or name.startswith(("notes/captures/", "notes/imports/"))
                or relative.name.startswith("ledger") and relative.suffix == ".json"):
            failures.append(name + ": private/generated artifact is tracked")
            continue  # Never open private configuration even if mistakenly tracked.
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            failures.append(name + ": missing or symlinked tracked file")
            continue
        file_count += 1
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                failures.append(name + ": possible " + label)  # Never print the value.
        if relative.suffix != ".md" or name.startswith("notes/"):
            continue
        text = data.decode("utf-8")
        if LOCAL_HOME.search(text):
            failures.append(name + ": machine-specific home path in documentation")
        for raw in MARKDOWN_LINK.findall(text):
            target = raw.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            linked = (path.parent / unquote(parsed.path)).resolve()
            try:
                linked.relative_to(ROOT)
            except ValueError:
                failures.append(name + ": link leaves repository")
                continue
            link_count += 1
            if not linked.exists():
                failures.append(name + ": missing link target " + parsed.path)
    for failure in failures:
        print("FAIL " + failure)
    print(f"Repository check: {file_count} files, {link_count} local links, {len(failures)} failures")
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
