"""A real MCP subprocess and protocol handshake against a disposable local service."""
import importlib.util
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HAS_MCP = sys.version_info >= (3, 11) and importlib.util.find_spec("mcp") is not None


@unittest.skipUnless(HAS_MCP, "Run the standard MCP integration in the Ultra venv")
class MCPTests(unittest.TestCase):
    def test_stdio_discovery_and_read_call_reach_local_registry_service(self):
        import anyio
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        observed = []
        class Service(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                observed.append((body, self.headers.get("Origin"), self.headers.get("X-Jarvis-MCP")))
                data = json.dumps({"active": False, "card": False}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        http = ThreadingHTTPServer(("127.0.0.1", 0), Service)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(http.server_port)
        async def exercise():
            script = str(Path(__file__).resolve().parents[1] / "tools/ultra_mcp.py")
            async with Client(StdioServerParameters(command=sys.executable, args=[script, "--url", url])) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 12)
                self.assertTrue(all('ctx' not in item.input_schema.get('properties',{}) for item in tools.tools))
                result = await client.call_tool("screen_watch_status", {})
                self.assertFalse(result.is_error)
                value = json.loads(next(item.text for item in result.content if item.type == "text"))
                self.assertEqual(value, {"active": False, "card": False})
                await client.call_tool("screen_watch_status", {})
        try:
            anyio.run(exercise)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=2)
        self.assertEqual(len(observed),2)
        session=observed[0][0]['operation_session']
        self.assertRegex(session,r'^[a-f0-9]{24}$')
        self.assertNotEqual(session,observed[1][0]['operation_session'])
        for body,origin,mcp_header in observed:
            self.assertRegex(body.pop('operation_session'),r'^[a-f0-9]{24}$')
            self.assertEqual((body,origin,mcp_header),({"name":"screen_watch_status","arguments":{}},url,"1"))


if __name__ == "__main__":
    unittest.main()
