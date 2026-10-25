"""Standard MCP stdio adapter for the running, loopback-only Jarvis server."""
import argparse
import json
import secrets
import hashlib
import hmac
import urllib.parse
import urllib.request
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_URL = "http://127.0.0.1:4700"
HTTP_TIMEOUT_S = 45
MAX_RESPONSE_BYTES = 50000
SESSION_ID_CHARS = 24
PROCESS_NONCE_BYTES = 32
MAX_REQUEST_ID_CHARS = 128
mcp = MCPServer("Ultra Jarvis")
server_url = DEFAULT_URL
process_nonce = secrets.token_bytes(PROCESS_NONCE_BYTES)


def call(name, arguments, ctx):
    # One budget/journal per transport request, rather than imposing a 15-minute
    # lifetime and 24-call limit on the entire long-lived MCP connection.
    request_id=ctx.request_id
    if type(request_id) not in (str,int) or len(str(request_id))>MAX_REQUEST_ID_CHARS:
        raise ToolError("Invalid MCP request identity.")
    operation_session=hmac.new(process_nonce,json.dumps([type(request_id).__name__,request_id]).encode(),hashlib.sha256).hexdigest()[:SESSION_ID_CHARS]
    request = urllib.request.Request(server_url + "/tools/call",
        data=json.dumps({"name": name, "arguments": arguments, "operation_session": operation_session}).encode(),
        headers={"Content-Type": "application/json", "Origin": server_url, "X-Jarvis-MCP": "1"})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            return json.loads(response.read(MAX_RESPONSE_BYTES))
    except Exception:
        raise ToolError("Jarvis is unavailable, the tool is disabled or the operation was not confirmed.") from None


@mcp.tool()
def notes_search(query: str, ctx: Context) -> dict:
    """Search local notes with semantic and keyword retrieval."""
    return call("notes_search", {"query": query}, ctx)


@mcp.tool()
def note_read(id: int, ctx: Context) -> dict:
    """Read a note passage and its revision before editing it."""
    return call("note_read", {"id": id}, ctx)


@mcp.tool()
def notes_capture(text: str, ctx: Context) -> dict:
    """Save a Markdown note explicitly requested by the user."""
    return call("notes_capture", {"text": text}, ctx)


@mcp.tool()
def note_write(id: int, text: str, revision: str, ctx: Context) -> dict:
    """Apply a requested note edit, checking the revision from note_read."""
    return call("note_write", {"id": id, "text": text, "revision": revision}, ctx)


@mcp.tool()
def preferences_get(ctx: Context) -> dict:
    """Read explicitly saved user preferences."""
    return call("preferences_get", {}, ctx)


@mcp.tool()
def preferences_set(key: str, value: str, ctx: Context) -> dict:
    """Remember an explicitly supplied preference; never store credentials."""
    return call("preferences_set", {"key": key, "value": value}, ctx)


@mcp.tool()
def preferences_forget(key: str, ctx: Context) -> dict:
    """Forget a user preference."""
    return call("preferences_forget", {"key": key}, ctx)


@mcp.tool()
def screen_watch_status(ctx: Context) -> dict:
    """Read screen watch state without capturing a frame."""
    return call("screen_watch_status", {}, ctx)


@mcp.tool()
def screen_watch_control(action: str, ctx: Context) -> dict:
    """Request start or stop in the open viewer; starting needs display-sharing permission."""
    return call("screen_watch_control", {"action": action}, ctx)


@mcp.tool()
def document_import(filename: str, ctx: Context) -> dict:
    """Import a PDF, DOCX or XLSX the user placed in .local/ultra-inbox. Filename only."""
    return call("document_import", {"filename": filename}, ctx)


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
