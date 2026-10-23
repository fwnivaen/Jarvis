"""List, run and resume bounded Jarvis workflows without exposing checkpoints."""
import argparse
import json
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:4700"
TIMEOUT_S = 310
MAX_RESPONSE_BYTES = 200000
MAX_IMPORT_BYTES = 16 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("templates", "runs", "run", "resume", "import"))
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--workflow", choices=("general", "research", "code", "document"))
    parser.add_argument("--question")
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    args = parser.parse_args()
    address = urllib.parse.urlsplit(args.url)
    if (address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost")
            or address.username or address.password or address.path not in ("", "/") or address.query or address.fragment):
        parser.error("Use the local Jarvis address.")
    url, body = args.url.rstrip("/"), None
    if args.action in ("run", "resume"):
        if not args.question or args.action == "resume" and not args.run_id:
            parser.error("Supply --question, and --run-id for resume. Use the original question when resuming.")
        path = "/chat"
        body = {"question": args.question}
        if args.workflow:
            body["workflow"] = args.workflow
        if args.run_id:
            body["resume_run"] = args.run_id
    elif args.action == "import":
        import base64
        from pathlib import Path
        if not args.file:
            parser.error("Supply --file /path/to/document.pdf")
        source = Path(args.file)
        if source.is_symlink() or not 0 < source.stat().st_size <= MAX_IMPORT_BYTES:
            parser.error("Use a regular document no larger than 16 MiB.")
        path = "/memory/import"
        body = {"filename": source.name, "data": base64.b64encode(source.read_bytes()).decode("ascii")}
    else:
        path = "/agents/workflows" if args.action == "templates" else "/agents/runs"
    request = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Origin": url})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            value = json.loads(response.read(MAX_RESPONSE_BYTES))
        print(json.dumps(value, indent=2, ensure_ascii=False))
    except Exception:
        parser.exit(1, "Jarvis is unavailable or refused this request. Check its flags and local state.\n")


if __name__ == "__main__":
    main()
