import json
import queue
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import server
import ultra
import ultra_tools
from codex_bridge import CodexBridge
from test_offline import request
from test_ultra import QUICK, response


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = replace(ultra.Settings(), enabled=True)
        self.writes = []
        self.registry = ultra_tools.Registry(lambda: self.settings, {
            "notes_capture": lambda text: self.writes.append(text) or {"saved": True},
            "notes_search": lambda query: {"notes": []}, "preferences_set": lambda key, value: {"saved": True}})

    def test_flags_types_unknown_tools_and_extra_arguments_fail_closed(self):
        for name, arguments in (("shell", {}), ("notes_capture", {"text": 4}),
                ("notes_capture", {"text": "a", "approval": True}), ("notes_search", {})):
            with self.assertRaises(ultra_tools.ToolError):
                self.registry.call(name, arguments)
        self.settings = replace(self.settings, tools_enabled=False)
        self.assertEqual(self.registry.catalog(), [])
        with self.assertRaises(ultra_tools.ToolError):
            self.registry.call("notes_capture", {"text": "a"})
        self.assertEqual(self.writes, [])

    def test_workers_and_retries_write_once_across_recovery(self):
        root = Path(self.temp.name)
        session = ultra_tools.ToolSession(self.registry, root=root)
        barrier = threading.Barrier(3)
        results = []
        def work():
            barrier.wait(timeout=2)
            results.append(session.call("notes_capture", {"text": "Remember this"}, time.monotonic()+2))
        threads = [threading.Thread(target=work) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
        self.assertEqual(len(results), 3)
        self.assertEqual(self.writes, ["Remember this"])
        recovered = ultra_tools.ToolSession(self.registry, session.identifier, root=root)
        self.assertTrue(recovered.call("notes_capture", {"text": "Remember this"}, time.monotonic()+2)["saved"])
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(session.path.stat().st_mode & 0o777, 0o600)

    def test_uncertain_write_is_never_replayed_and_deadline_blocks_actions(self):
        session = ultra_tools.ToolSession(self.registry, root=Path(self.temp.name))
        self.registry.callbacks["notes_capture"] = lambda text: (_ for _ in ()).throw(OSError("private"))
        for _ in range(2):
            with self.assertRaises(ultra_tools.ToolError):
                session.call("notes_capture", {"text": "once"}, time.monotonic()+2)
        self.assertEqual(session.count, 1)
        with self.assertRaises(ultra_tools.ToolError):
            session.call("notes_capture", {"text": "expired"}, time.monotonic()-1)
        self.assertEqual(session.count, 1)

    def test_local_http_requires_origin_but_no_action_approval(self):
        with patch.object(server, "TOOLS", self.registry):
            body = {"name": "notes_capture", "arguments": {"text": "Explicit request"}}
            self.assertEqual(request("/tools/call", "POST", body)[0], 403)
            status, _, raw = request("/tools/call", "POST", body, headers={"Origin": "http://127.0.0.1:4700"})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(raw)["saved"])
            self.assertEqual(request("/tools/call", "POST", body, headers={"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.writes, ["Explicit request"])

    def test_model_import_is_confined_to_inbox(self):
        with self.assertRaises(ValueError):
            server.tool_document_import("../../config.json")
        with self.assertRaises(ValueError):
            server.tool_document_import("/tmp/report.pdf")

    def test_dynamic_tool_protocol_handles_only_registered_calls(self):
        bridge = CodexBridge(None)
        bridge._scratch = SimpleNamespace(name="/empty-workspace")
        bridge._models = {QUICK: {"supportedReasoningEfforts": [{"reasoningEffort": "high"}]}}
        sent, calls = [], []
        def rpc(method, params, deadline):
            if method == "thread/start":
                self.assertEqual(params["dynamicTools"], self.registry.dynamic_specs())
                return {"thread": {"id": "thread"}}
            if method == "turn/start":
                bridge._calls["thread"].put(("tool_call", {"id": 77, "params": {
                    "threadId": "thread", "turnId": "turn", "callId": "call", "tool": "notes_search", "arguments": {"query": "budget"}}}))
                bridge._calls["thread"].put(("answer", json.dumps(response())))
                bridge._calls["thread"].put(("done", "completed"))
                return {"turn": {"id": "turn"}}
            return {}
        def handle(name, arguments, deadline):
            calls.append(name)
            return self.registry.call(name, arguments)
        with patch.object(bridge, "start"), patch.object(bridge, "_rpc", side_effect=rpc), patch.object(bridge, "_send", side_effect=sent.append):
            result = bridge.complete(model=QUICK, effort="high", system="test", payload={}, schema=ultra.CHECKED_SCHEMA,
                deadline=time.monotonic()+2, observer=lambda _: None, tools=self.registry.dynamic_specs(), tool_handler=handle)
        self.assertEqual(json.loads(result)["answer"], "Ready.")
        self.assertEqual(calls, ["notes_search"])
        self.assertTrue(sent[0]["result"]["success"])
        self.assertEqual(sent[0]["result"]["contentItems"][0]["type"], "inputText")
        self.assertEqual(bridge._tool_threads, set())
        bridge._scratch = None

    def test_builtin_tools_stay_blocked_even_with_local_tools(self):
        bridge = CodexBridge(None)
        bridge._calls["thread"] = queue.Queue()
        bridge._tool_threads.add("thread")
        bridge._dispatch({"method": "item/started", "params": {"threadId": "thread", "item": {"type": "commandExecution"}}}, None)
        self.assertEqual(bridge._calls["thread"].get_nowait(), ("blocked_action", None))

    def test_slow_local_tool_does_not_extend_worker_wait(self):
        bridge = CodexBridge(None)
        bridge._scratch = SimpleNamespace(name="/empty-workspace")
        bridge._models = {QUICK: {"supportedReasoningEfforts": [{"reasoningEffort": "high"}]}}
        release = threading.Event()
        def rpc(method, params, deadline):
            if method == "thread/start":
                return {"thread": {"id": "thread"}}
            if method == "turn/start":
                bridge._calls["thread"].put(("tool_call", {"id": 7, "params": {
                    "tool": "notes_search", "arguments": {"query": "x"}, "turnId": "turn"}}))
                return {"turn": {"id": "turn"}}
            return {}
        started = time.monotonic()
        try:
            with patch.object(bridge, "start"), patch.object(bridge, "_rpc", side_effect=rpc):
                with self.assertRaisesRegex(ultra.BridgeError, "timeout"):
                    bridge.complete(model=QUICK, effort="high", system="test", payload={}, schema=ultra.CHECKED_SCHEMA,
                        deadline=started + .05, observer=lambda _: None, tools=self.registry.dynamic_specs(),
                        tool_handler=lambda *_: release.wait(timeout=1))
            self.assertLess(time.monotonic() - started, .5)
        finally:
            release.set()
            bridge._scratch = None


if __name__ == "__main__":
    unittest.main()
