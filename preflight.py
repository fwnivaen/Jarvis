"""Offline security and behavior checks. Does not call a model or read secrets."""
import contextlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build
import server

ROOT = Path(__file__).resolve().parent
MIN_SAMPLE_NOTES = 30
MIN_GROUPS = 5
TEST_PORT = 4700
TEST_NOTE_ID = 2
TEST_TIMEOUT_S = 10
REQUEST_LIMIT_EXCESS = 1


class FakeSocket:
    def __init__(self, data):
        self.input = io.BytesIO(data)
        self.output = io.BytesIO()

    def makefile(self, *_args):
        return self.input

    def sendall(self, data):
        self.output.write(data)

    def settimeout(self, _timeout):
        pass


def request(path, method="GET", body=None, headers=None):
    class TestServer:
        server_address = ("127.0.0.1", TEST_PORT)
    fields = {"Host": f"127.0.0.1:{TEST_PORT}"}
    data = b"" if body is None else json.dumps(body).encode()
    if body is not None:
        fields.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
    fields.update(headers or {})
    raw = f"{method} {path} HTTP/1.0\r\n" + "".join(f"{k}: {v}\r\n" for k, v in fields.items()) + "\r\n"
    sock = FakeSocket(raw.encode() + data)
    server.Handler(sock, ("127.0.0.1", TEST_PORT), TestServer())
    response_headers, response_body = sock.output.getvalue().split(b"\r\n\r\n", 1)
    return int(response_headers.split()[1]), response_headers.decode(), response_body


class Preflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.NOTES, cls.graph = build.build()

    def test_graph_indices_and_edges(self):
        nodes, links = self.graph["nodes"], self.graph["links"]
        self.assertGreaterEqual(len(nodes), MIN_SAMPLE_NOTES)
        self.assertGreaterEqual(len({n["group"] for n in nodes}), MIN_GROUPS)
        self.assertEqual([n["id"] for n in nodes], list(range(len(nodes))))
        self.assertTrue(all(len(n["excerpt"]) <= build.EXCERPT_CHARS for n in nodes))
        self.assertTrue(links)
        for link in links:
            self.assertTrue(0 <= link["source"] < link["target"] < len(nodes))
        self.assertEqual(len(links), len({(l["source"], l["target"]) for l in links}))

    def test_title_mentions_shared_wikilinks_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "notes"
            root.mkdir()
            (root / "Alpha.md").write_text("Beta is useful. [[Shared Topic|alias]]")
            (root / "Beta.md").write_text("Independent text")
            (root / "Gamma.md").write_text("[[Shared Topic#Heading]]")
            outside = Path(directory) / "outside.md"
            outside.write_text("Must not be indexed")
            (root / "Link.md").symlink_to(outside)
            graph = build.make_graph(build.read_notes(root))
            self.assertEqual([n["label"] for n in graph["nodes"]], ["Alpha", "Beta", "Gamma"])
            self.assertEqual(graph["links"], [{"source": 0, "target": 1}, {"source": 0, "target": 2}])

    def test_title_weighting_and_followup(self):
        selection = server.retrieve("What does Menu Pricing say?", [])
        self.assertEqual(selection[0]["title"], "Menu Pricing")
        self.assertLessEqual(len(selection), server.TOP_NOTES)
        followup = server.retrieve("Who updates it?", [{"question": "Explain Cash Flow Forecast", "answer": ""}])
        self.assertIn("Cash Flow Forecast", [n["title"] for n in followup])
        self.assertEqual(server.retrieve("quasar nucleosynthesis", []), [])

    def test_answer_validation(self):
        notes = [{"id": TEST_NOTE_ID}]
        self.assertEqual(server.validate_answer('{"answer":"A supported answer.","nodes":[2]}', notes)["nodes"], [TEST_NOTE_ID])
        invalid = ('plain prose', '{"answer":"","nodes":[]}', '{"answer":"x","nodes":[999]}',
                   '{"answer":"x","nodes":[true]}', '{"answer":"x","nodes":[],"extra":1}')
        for raw in invalid:
            with self.assertRaises(server.BrainError):
                server.validate_answer(raw, notes)

    def test_public_routes_and_secrets_boundary(self):
        self.assertEqual(request("/")[0], 200)
        self.assertEqual(request("/graph-data.js")[0], 200)
        for path in ("/config.json", "/../config.json", "/%2e%2e/config.json", "/%63onfig.json",
                     "/.git/config", "/server.py", "/AGENTS.md", "/notes/", "/viewer/", "/anything.json"):
            self.assertEqual(request(path)[0], 404, path)
        self.assertEqual(request("/", headers={"Host": "attacker.example"})[0], 403)
        status, headers, body = request("/", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertIn("X-Content-Type-Options: nosniff", headers)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "index.html").symlink_to(ROOT / "README.md")
            with patch.object(server, "VIEWER_DIR", Path(directory)):
                self.assertEqual(request("/")[0], 404)

    def test_chat_input_and_origin_validation(self):
        for body in ({}, {"question": ""}, {"question": []}, [], {"question": "x" * (server.MAX_QUESTION_CHARS + REQUEST_LIMIT_EXCESS)}):
            self.assertEqual(request("/chat", "POST", body)[0], 400)
        self.assertEqual(request("/chat", "POST", {"question": "test"}, {"Origin": "https://attacker.example"})[0], 403)
        self.assertEqual(request("/chat", "POST", {"question": "test"}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(request("/chat", "POST", {"question": "test"}, {"Content-Length": str(server.MAX_REQUEST_BYTES + REQUEST_LIMIT_EXCESS)})[0], 400)

    def test_session_history_isolation_and_brain_errors(self):
        server.SESSIONS.clear()
        histories = []
        def fake_brain(_system, notes, history, _question):
            histories.append(history)
            return {"answer": "The notes cover this. Here is the summary.", "nodes": [notes[0]["id"]]}
        with patch.object(server, "ask_brain", side_effect=fake_brain):
            status, headers, _ = request("/chat", "POST", {"question": "Menu Pricing"})
            self.assertEqual(status, 200)
            cookie = re.search(r"Set-Cookie: ([^;]+)", headers).group(1)
            request("/chat", "POST", {"question": "What about it?"}, {"Cookie": cookie})
            request("/chat", "POST", {"question": "Quarterly Goals"})
        self.assertEqual(len(histories[0]), 0)
        self.assertEqual(len(histories[1]), 1)
        self.assertEqual(len(histories[2]), 0)
        with patch.object(server, "ask_brain", return_value={"answer": "Unavailable.", "nodes": [], "error": True}):
            self.assertEqual(request("/chat", "POST", {"question": "Menu Pricing"})[0], 503)

    def test_codex_arguments_are_restricted(self):
        args = server.cli_command("codex", "gpt-6-astra", "/tmp/empty", "/tmp/schema.json", "/tmp/answer.txt")
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertIn("--ignore-user-config", args)
        self.assertIn("--strict-config", args)
        self.assertIn("--ephemeral", args)
        self.assertIn('web_search="disabled"', args)
        for feature in ("shell_tool", "apps", "plugins", "browser_use", "computer_use", "multi_agent"):
            self.assertIn(feature, args)
        self.assertEqual(args[-1], "-")

    def test_missing_cli_and_timeout_are_safe(self):
        safe_config = {"brain": "codex-cli", "model": "gpt-6-astra"}
        with patch.object(server, "load_config", return_value=safe_config), patch.object(server, "find_codex", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            result = server.ask_brain("system", [], [], "test")
            self.assertTrue(result["error"])
            self.assertEqual(result["nodes"], [])
        class TimedOut:
            pid = 123
            returncode = None
            def __init__(self, *_args, **_kwargs):
                self.first = True
            def communicate(self, *_args, **_kwargs):
                if self.first:
                    self.first = False
                    raise subprocess.TimeoutExpired("codex", server.BRAIN_TIMEOUT_S)
                return None, ""
        with patch.object(server, "load_config", return_value=safe_config), patch.object(server, "find_codex", return_value="codex"), patch.object(server.subprocess, "Popen", TimedOut), patch.object(server.os, "killpg"), contextlib.redirect_stdout(io.StringIO()):
            result = server.ask_brain("system", [], [], "test")
            self.assertTrue(result["error"])
            self.assertIn("too long", result["answer"])

    def test_ignored_files_are_untracked(self):
        for name in ("config.json", "viewer/graph-data.js"):
            result = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT, timeout=TEST_TIMEOUT_S)
            self.assertEqual(result.returncode, 0)
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", name], cwd=ROOT, capture_output=True, timeout=TEST_TIMEOUT_S)
            self.assertNotEqual(tracked.returncode, 0)

    def test_viewer_javascript_syntax(self):
        page = (ROOT / "viewer" / "index.html").read_text()
        script = re.search(r'<script type="module">(.*?)</script>', page, re.S).group(1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "viewer.mjs"
            path.write_text(script)
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=TEST_TIMEOUT_S)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Preflight)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    state = "PASS" if result.wasSuccessful() else "FAIL"
    print(f"PREFLIGHT {state}: {result.testsRun} checks; {len(server.NOTES)} notes; offline checks only — live browser and brain require separate verification.")
    raise SystemExit(0 if result.wasSuccessful() else 1)
