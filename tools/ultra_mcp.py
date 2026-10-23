"""Standard MCP stdio adapter for the running, loopback-only Jarvis server."""
import argparse
import json
import urllib.parse
import urllib.request
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_URL = "http://127.0.0.1:4700"
HTTP_TIMEOUT_S = 45
MAX_RESPONSE_BYTES = 50000
mcp = MCPServer("Ultra Jarvis")
server_url = DEFAULT_URL


def call(name, arguments):
    request = urllib.request.Request(server_url + "/tools/call",
        data=json.dumps({"name": name, "arguments": arguments}).encode(),
        headers={"Content-Type": "application/json", "Origin": server_url, "X-Jarvis-MCP": "1"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            return json.loads(response.read(MAX_RESPONSE_BYTES))
    except Exception:
        raise ToolError("Jarvis is unavailable, the tool is disabled or the operation was not confirmed.") from None


@mcp.tool()
def notes_search(query: str) -> dict:
    """Search local notes with semantic and keyword retrieval."""
    return call("notes_search", {"query": query})


@mcp.tool()
def note_read(id: int) -> dict:
    """Read a note passage and its revision before editing it."""
    return call("note_read", {"id": id})


@mcp.tool()
def notes_capture(text: str) -> dict:
    """Save a Markdown note explicitly requested by the user."""
    return call("notes_capture", {"text": text})


@mcp.tool()
def note_write(id: int, text: str, revision: str) -> dict:
    """Apply a requested note edit, checking the revision from note_read."""
    return call("note_write", {"id": id, "text": text, "revision": revision})


@mcp.tool()
def preferences_get() -> dict:
    """Read explicitly saved user preferences."""
    return call("preferences_get", {})


@mcp.tool()
def preferences_set(key: str, value: str) -> dict:
    """Remember an explicitly supplied preference; never store credentials."""
    return call("preferences_set", {"key": key, "value": value})


@mcp.tool()
def preferences_forget(key: str) -> dict:
    """Forget a user preference."""
    return call("preferences_forget", {"key": key})


@mcp.tool()
def focus_status() -> dict:
    """Read the existing Focus session status."""
    return call("focus_status", {})


@mcp.tool()
def focus_control(action: str, seconds: int | None = None) -> dict:
    """Start, pause, resume, end, abort or retarget Focus at the user's request."""
    arguments = {"action": action}
    if seconds is not None:
        arguments["seconds"] = seconds
    return call("focus_control", arguments)


@mcp.tool()
def screen_watch_status() -> dict:
    """Read screen watch state without capturing a frame."""
    return call("screen_watch_status", {})


@mcp.tool()
def screen_watch_control(action: str) -> dict:
    """Request start or stop in the open viewer; starting needs display-sharing permission."""
    return call("screen_watch_control", {"action": action})


@mcp.tool()
def document_import(filename: str) -> dict:
    """Import a PDF, DOCX or XLSX the user placed in .local/ultra-inbox. Filename only."""
    return call("document_import", {"filename": filename})


def main():
    global server_url
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.url)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        parser.error("Use the local Jarvis HTTP address.")
    server_url = args.url.rstrip("/")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
