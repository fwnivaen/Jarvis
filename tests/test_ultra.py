"""Ultra behavior tests: no network, credentials, real models or real tools."""
import io
import json
import queue
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ultra
import server
from codex_bridge import BridgeError, CodexBridge
from ultra_monitor import Monitor, table
from test_offline import request

QUICK = "gpt-6-luna"
BRAIN = "gpt-6.1-sol"
ASTRA = "gpt-6-astra"
WORKERS = 3
TEST_WAIT_S = 2
NOTES = [{"id": 7, "title": "Budget", "text": "The budget is 120 pounds. Revenue is 200 pounds."}]
SECRET = "PRIVATE_PROMPT_AND_REASONING_SENTINEL"


def response(answer="Ready.", note=False):
    return {"answer": answer, "about_notes": note, "nodes": [7] if note else [],
        "evidence": [{"node": 7, "quote": "The budget is 120 pounds."}] if note else [], "calculations": []}


def dispatch(route="direct", job="general"):
    return {"route": route, "job": job, "response": response()}


class FakeBridge:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.lock = threading.Lock()

    def complete(self, **call):
        with self.lock:
            self.calls.append(call)
        call["observer"]({"inputTokens": 10, "outputTokens": 4, "totalTokens": 14})
        value = self.handler(call)
        return json.dumps(value) if not isinstance(value, str) else value

    def close(self):
        pass


class RoutingTests(unittest.TestCase):
    def setUp(self):
        # The original routing contract remains available behind the profile flag.
        self.settings = replace(ultra.Settings(), enabled=True, terminal_monitor_enabled=False,
            crew_profiles_enabled=False, collaboration_enabled=False, structured_reports_enabled=False,
            workflows_enabled=False, checkpoint_enabled=False, evaluation_enabled=False)

    def run_request(self, handler, **kwargs):
        fake = FakeBridge(handler)
        runtime = ultra.UltraJarvis(lambda: fake)
        value = runtime.answer(self.settings, "Answer from notes.", NOTES, [], "Question", **kwargs)
        return value, fake, runtime

    def test_simple_question_uses_one_cheap_call_and_no_workers(self):
        value, fake, runtime = self.run_request(lambda _: dispatch())
        self.assertEqual(value["answer"], "Ready.")
        self.assertEqual([c["model"] for c in fake.calls], [QUICK])
        self.assertEqual(fake.calls[0]["effort"], "high")
        self.assertEqual(value["ultra"]["workers"], 0)
        self.assertFalse(runtime.monitor.snapshot()["active"])
        self.assertEqual(runtime.monitor.snapshot()["agents"][0]["total_tokens"], 14)

    def test_parallel_workers_overlap_and_brain_checks_final_answer(self):
        barrier = threading.Barrier(WORKERS)
        def handle(call):
            if call["schema"] is ultra.DISPATCH_SCHEMA:
                return dispatch("brain")
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": f"Read part {i}", "kind": "general"} for i in range(WORKERS)]}
            if "assignment" in call["payload"]:
                barrier.wait(timeout=TEST_WAIT_S)
                return response(note=True)
            self.assertEqual(call["model"], BRAIN)
            self.assertEqual(len(call["payload"]["worker_results"]), WORKERS)
            return response("Verified budget.", note=True)
        value, fake, runtime = self.run_request(handle)
        self.assertEqual(value["nodes"], [7])
        self.assertEqual(value["ultra"]["workers"], WORKERS)
        self.assertEqual(sum("assignment" in c["payload"] for c in fake.calls), WORKERS)
        self.assertTrue(all(c["effort"] == "high" for c in fake.calls))
        self.assertTrue(all(r["status"] == "complete" for r in runtime.monitor.snapshot()["agents"]))

    def test_code_work_uses_sol_even_if_dispatch_calls_it_direct(self):
        def handle(call):
            if call["schema"] is ultra.DISPATCH_SCHEMA:
                return dispatch("direct", "code")
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": "Review code", "kind": "code"}]}
            return response()
        _, fake, _ = self.run_request(handle)
        self.assertEqual([c["model"] for c in fake.calls], [QUICK, BRAIN, BRAIN, BRAIN])

    def test_explicit_workers_cannot_be_downgraded_to_cheap_direct_chat(self):
        def handle(call):
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": "Read supplied note", "kind": "general"}]}
            self.assertIsNot(call["schema"], ultra.DISPATCH_SCHEMA)
            return response()
        fake = FakeBridge(handle)
        runtime = ultra.UltraJarvis(lambda: fake)
        value = runtime.answer(self.settings, "Test", NOTES, [], "Use three parallel workers to analyze the notes.")
        self.assertEqual(value["ultra"]["workers"], 1)
        self.assertEqual(fake.calls[0]["model"], BRAIN)

    def test_parallel_off_uses_one_brain_call_after_classification(self):
        self.settings = replace(self.settings, parallel_workers_enabled=False)
        _, fake, _ = self.run_request(lambda call: dispatch("brain") if call["schema"] is ultra.DISPATCH_SCHEMA else response())
        self.assertEqual([c["model"] for c in fake.calls], [QUICK, BRAIN])

    def test_explicit_no_workers_is_respected(self):
        fake = FakeBridge(lambda c: dispatch("brain") if c["schema"] is ultra.DISPATCH_SCHEMA else response())
        runtime = ultra.UltraJarvis(lambda: fake)
        value = runtime.answer(self.settings, "Test", NOTES, [], "Do not use workers; analyze this code.")
        self.assertEqual(value["ultra"]["workers"], 0)
        self.assertEqual(len(fake.calls), 2)

    def test_uncertain_prose_does_not_escalate(self):
        output = dispatch()
        output["response"]["answer"] = "I'm unsure; the notes do not cover that."
        value, fake, _ = self.run_request(lambda _: output)
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(value["ultra"]["escalations"], 0)

    def test_bad_citation_is_an_objective_failure_with_one_promotion(self):
        invalid = dispatch()
        invalid["response"].update(about_notes=True, nodes=[999])
        value, fake, _ = self.run_request(lambda c: invalid if c["model"] == QUICK else dispatch())
        self.assertFalse(value.get("error"))
        self.assertEqual([c["model"] for c in fake.calls], [QUICK, BRAIN])
        self.assertEqual(value["ultra"]["escalations"], 1)

    def test_racing_workers_share_one_escalation_budget(self):
        def handle(call):
            if call["schema"] is ultra.DISPATCH_SCHEMA:
                return dispatch("brain")
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": str(i), "kind": "general"} for i in range(WORKERS)]}
            if "assignment" in call["payload"] and call["model"] == QUICK:
                bad = response(note=True)
                bad["evidence"][0]["quote"] = "Invented source"
                return bad
            return response()
        value, fake, runtime = self.run_request(handle)
        self.assertEqual(value["ultra"]["escalations"], 1)
        self.assertTrue(value["partial"])
        self.assertNotIn(ASTRA, [c["model"] for c in fake.calls])
        promoted = [r for r in runtime.monitor.snapshot()["agents"] if r["role"] == "worker" and r["model"] == BRAIN]
        self.assertEqual(len(promoted), 1)

    def test_transport_retries_are_bounded_and_do_not_promote(self):
        def fail(_):
            raise BridgeError("inference_failed")
        value, fake, runtime = self.run_request(fail)
        self.assertTrue(value["error"])
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(set(c["model"] for c in fake.calls), {QUICK})
        self.assertEqual(len(set(c["deadline"] for c in fake.calls)), 1)
        self.assertLessEqual(fake.calls[0]["deadline"], time.monotonic() + 45)
        self.assertEqual(runtime.monitor.snapshot()["agents"][0]["retries"], 2)
        self.assertEqual(runtime.monitor.snapshot()["agents"][0]["total_tokens"], 42)

    def test_tool_attempt_is_refused_without_retry(self):
        def blocked(_):
            raise BridgeError("blocked_action")
        value, fake, _ = self.run_request(blocked)
        self.assertTrue(value["error"])
        self.assertEqual(len(fake.calls), 1)

    def test_astra_requires_explicit_manual_override(self):
        value, fake, _ = self.run_request(lambda _: response(), manual_model=ASTRA)
        self.assertFalse(value.get("error"))
        self.assertEqual([c["model"] for c in fake.calls], [ASTRA])
        self.assertEqual(value["ultra"]["workers"], 0)

    def test_vision_uses_luna_and_only_automatic_duplicates_are_skipped(self):
        fake = FakeBridge(lambda _: response())
        runtime = ultra.UltraJarvis(lambda: fake)
        def ask(**extra):
            return runtime.answer(self.settings, "Look", [], [], "What changed?", image=b"jpeg", kind="screen", **extra)
        self.assertFalse(ask(automatic=True, watch_token="watch-token-1").get("skipped"))
        self.assertTrue(ask(automatic=True, watch_token="watch-token-1")["skipped"])
        ask()
        ask(automatic=True, watch_token="watch-token-2")
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(set(c["model"] for c in fake.calls), {QUICK})
        self.assertEqual(set(c["effort"] for c in fake.calls), {"high"})
        self.assertNotIn(b"jpeg", runtime._frames)

    def test_flags_restore_existing_brain_and_manual_non_codex_backend(self):
        with patch.object(server.ultra.Settings, "read", return_value=(ultra.Settings(), None)), patch.object(server, "ask_brain", return_value={"legacy": True}) as legacy:
            self.assertEqual(server.answer_request("system", [], [], "hello"), {"legacy": True})
            legacy.assert_called_once_with("system", [], [], "hello")
        with patch.object(server.ultra.Settings, "read", return_value=(self.settings, None)), patch.object(server, "ACTIVE_BRAIN", ("openrouter", "manual")), patch.object(server, "ask_brain", return_value={"legacy": True}):
            self.assertEqual(server.answer_request("system", [], [], "hello"), {"legacy": True})


class CrewRoutingTests(unittest.TestCase):
    def setUp(self):
        self.settings = replace(ultra.Settings(), enabled=True, terminal_monitor_enabled=False,
            collaboration_enabled=False, structured_reports_enabled=False, workflows_enabled=False,
            checkpoint_enabled=False, evaluation_enabled=False)

    def test_profiles_leave_cheap_direct_vision_and_manual_override_at_high(self):
        fake = FakeBridge(lambda call: dispatch() if call["schema"] is ultra.DISPATCH_SCHEMA else response())
        runtime = ultra.UltraJarvis(lambda: fake)
        runtime.answer(self.settings, "Test", NOTES, [], "Hello")
        runtime.answer(self.settings, "Test", [], [], "Look", image=b"jpeg", kind="screen")
        runtime.answer(self.settings, "Test", NOTES, [], "Hello", manual_model=ASTRA)
        self.assertEqual([(call["model"], call["effort"]) for call in fake.calls],
            [(QUICK, "high"), (QUICK, "high"), (ASTRA, "high")])
        self.assertIsNone(runtime.monitor.snapshot()["agents"][0]["slot"])

    def test_boss_shares_request_deadline_while_worker_retries_share_45_second_limit(self):
        def handle(call):
            if call["schema"] is ultra.DISPATCH_SCHEMA:
                return dispatch("brain")
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": "Review", "kind": "general"}]}
            if "assignment" in call["payload"] and "validation_feedback" not in call["payload"]:
                raise BridgeError("inference_failed")
            return response()
        fake = FakeBridge(handle)
        runtime = ultra.UltraJarvis(lambda: fake)
        # A fixed clock verifies boundaries without depending on machine timing.
        with patch.object(ultra.time, "monotonic", return_value=100):
            value = runtime.answer(self.settings, "Test", NOTES, [], "Review the supplied note.")
        self.assertFalse(value.get("error"))
        bosses = [call for call in fake.calls if "tasks" in call["schema"]["properties"] or "worker_results" in call["payload"]]
        workers = [call for call in fake.calls if "assignment" in call["payload"]]
        self.assertEqual([call["deadline"] for call in bosses], [340, 340])
        self.assertEqual([call["deadline"] for call in workers], [145, 145])
        self.assertEqual(fake.calls[0]["deadline"], 145)

    def test_exact_three_worker_profiles_run_in_parallel_and_boss_uses_max(self):
        barrier = threading.Barrier(WORKERS)
        def handle(call):
            if call["schema"] is ultra.DISPATCH_SCHEMA:
                return dispatch("brain")
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": str(i), "kind": "code"} for i in range(WORKERS)]}
            if "assignment" in call["payload"]:
                barrier.wait(timeout=TEST_WAIT_S)
            return response()
        fake = FakeBridge(handle)
        runtime = ultra.UltraJarvis(lambda: fake)
        value = runtime.answer(self.settings, "Test", NOTES, [], "Review this code.")
        self.assertFalse(value.get("error"))
        workers = {int(call["payload"]["assignment"]): (call["model"], call["effort"])
            for call in fake.calls if "assignment" in call["payload"]}
        self.assertEqual(workers, {0: (BRAIN, "medium"), 1: (QUICK, "max"), 2: (QUICK, "high")})
        bosses = [call for call in fake.calls if "tasks" in call["schema"]["properties"] or "worker_results" in call["payload"]]
        self.assertEqual([(call["model"], call["effort"]) for call in bosses], [(BRAIN, "max"), (BRAIN, "max")])
        self.assertEqual((fake.calls[0]["model"], fake.calls[0]["effort"]), (QUICK, "high"))
        rows = runtime.public_state(self.settings)["agents"]
        self.assertEqual([row["slot"] for row in rows if row["role"] in ("brain", "answer")], ["boss", "boss"])
        self.assertEqual({row["slot"]: (row["model"], row["effort"]) for row in rows if row["role"] == "worker"},
            {"worker-1": (BRAIN, "medium"), "worker-2": (QUICK, "max"), "worker-3": (QUICK, "high")})

    def test_objective_promotion_keeps_slot_and_reports_effective_sol_medium(self):
        def handle(call):
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": str(i), "kind": "general"} for i in range(WORKERS)]}
            if call["payload"].get("assignment") == "1" and call["model"] == QUICK:
                invalid = response(note=True)
                invalid["evidence"][0]["quote"] = "Invented source"
                return invalid
            return response()
        fake = FakeBridge(handle)
        runtime = ultra.UltraJarvis(lambda: fake)
        value = runtime.answer(self.settings, "Test", NOTES, [], "Use three workers.")
        self.assertFalse(value.get("error"))
        self.assertEqual(value["ultra"]["escalations"], 1)
        promoted = [row for row in runtime.monitor.snapshot()["agents"] if row["slot"] == "worker-2"]
        self.assertEqual(len(promoted), 1)
        self.assertEqual((promoted[0]["model"], promoted[0]["effort"], promoted[0]["retries"]), (BRAIN, "medium", 1))
        self.assertNotIn(ASTRA, [call["model"] for call in fake.calls])

    def test_no_workers_uses_boss_max_but_keeps_cheap_classifier(self):
        fake = FakeBridge(lambda call: dispatch("brain") if call["schema"] is ultra.DISPATCH_SCHEMA else response())
        runtime = ultra.UltraJarvis(lambda: fake)
        runtime.answer(self.settings, "Test", NOTES, [], "Do not use workers; analyze this code.")
        self.assertEqual([(call["model"], call["effort"]) for call in fake.calls], [(QUICK, "high"), (BRAIN, "max")])
        self.assertEqual(runtime.monitor.snapshot()["agents"][-1]["slot"], "boss")

    def test_crew_roster_honors_flags_limit_and_profile_fallback(self):
        runtime = ultra.UltraJarvis(lambda: None)
        roster = runtime.public_state(self.settings)["crew"]
        self.assertEqual([(member["id"], member["model"], member["effort"]) for member in roster],
            [("boss", BRAIN, "max"), ("worker-1", BRAIN, "medium"), ("worker-2", QUICK, "max"), ("worker-3", QUICK, "high")])
        for flag in ("enabled", "routing_enabled", "live_monitor_enabled", "crew_visual_enabled"):
            state = runtime.public_state(replace(self.settings, **{flag: False}))
            self.assertFalse(state["crew_enabled"])
            self.assertEqual(state["crew"], [])
        limited = runtime.public_state(replace(self.settings, max_workers=2))
        self.assertEqual([member["id"] for member in limited["crew"]], ["boss", "worker-1", "worker-2"])
        sequential = runtime.public_state(replace(self.settings, parallel_workers_enabled=False))
        self.assertEqual([member["id"] for member in sequential["crew"]], ["boss"])
        fallback = runtime.public_state(replace(self.settings, crew_profiles_enabled=False))["crew"]
        self.assertEqual([(member["model"], member["effort"]) for member in fallback],
            [(BRAIN, "high"), (QUICK, "high"), (QUICK, "high"), (QUICK, "high")])
        expanded = runtime.public_state(replace(self.settings, max_workers=5))["crew"]
        self.assertEqual([(member["model"], member["effort"]) for member in expanded[4:]], [(QUICK, "high"), (QUICK, "high")])


class ValidationTests(unittest.TestCase):
    def test_arithmetic_is_checked_without_executing_code(self):
        valid = response()
        valid["calculations"] = [{"expression": "(200 - 120) / 200 * 100", "result": "40"}]
        self.assertEqual(ultra.checked(valid, NOTES)["answer"], "Ready.")
        valid["calculations"][0]["result"] = "50"
        with self.assertRaisesRegex(ultra.CheckFailure, "math_check"):
            ultra.checked(valid, NOTES)
        valid["calculations"] = [{"expression": "100 / 3", "result": "33.33"}]
        self.assertEqual(ultra.checked(valid, NOTES)["answer"], "Ready.")
        valid["calculations"] = [{"expression": "__import__('os').system('bad')", "result": "0"}]
        with self.assertRaisesRegex(ultra.CheckFailure, "math_check"):
            ultra.checked(valid, NOTES)

    def test_quotes_must_exist_and_every_citation_needs_evidence(self):
        self.assertEqual(ultra.checked(response(note=True), NOTES)["nodes"], [7])
        for evidence in ([], [{"node": 7, "quote": "invented"}], [{"node": 8, "quote": "The budget is 120 pounds."}]):
            value = response(note=True)
            value["evidence"] = evidence
            with self.assertRaisesRegex(ultra.CheckFailure, "missing_sources"):
                ultra.checked(value, NOTES)

    def test_invalid_config_disables_ultra_instead_of_selecting_an_unverified_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ultra.json"
            for fields in ({"enabled": "false"}, {"quick_model": ASTRA}, {"max_workers": 99},
                           {"worker_retries": 3}, {"max_escalations": 2}, {"worker_timeout_s": 46},
                           {"unexpected": True}, {"crew_profiles_enabled": "true"}, {"crew_visual_enabled": 1}):
                values = {"enabled": True}
                values.update(fields)
                path.write_text(json.dumps(values))
                settings, notice = ultra.Settings.read(path)
                self.assertFalse(settings.enabled)
                self.assertEqual(notice, "invalid_config")
            path.write_text(json.dumps({"enabled": True, "max_workers": 4}))
            self.assertEqual(ultra.Settings.read(path)[0].max_workers, 4)


class MonitorAndProtocolTests(unittest.TestCase):
    def test_timeout_interrupts_turn_and_unsubscribes_before_returning(self):
        bridge = CodexBridge(None)
        bridge._scratch = SimpleNamespace(name="/temporary-empty-workspace")
        bridge._models = {QUICK: {"supportedReasoningEfforts": [{"reasoningEffort": "high"}]}}
        methods = []
        def rpc(method, _params, _deadline):
            methods.append(method)
            if method == "thread/start":
                return {"thread": {"id": "test-thread"}, "model": QUICK}
            if method == "turn/start":
                return {"turn": {"id": "test-turn"}}
            return {}
        with patch.object(bridge, "start"), patch.object(bridge, "_rpc", side_effect=rpc):
            with self.assertRaisesRegex(BridgeError, "timeout"):
                bridge.complete(model=QUICK, effort="high", system="Synthetic test", payload={},
                    schema=ultra.CHECKED_SCHEMA, deadline=time.monotonic(), observer=lambda _: None)
        self.assertEqual(methods, ["thread/start", "turn/start", "turn/interrupt", "thread/unsubscribe"])
        self.assertEqual(bridge._calls, {})
        bridge._scratch = None

    def test_partial_answer_from_failed_turn_is_never_accepted(self):
        bridge = CodexBridge(None)
        bridge._scratch = SimpleNamespace(name="/temporary-empty-workspace")
        bridge._models = {QUICK: {"supportedReasoningEfforts": [{"reasoningEffort": "high"}]}}
        def rpc(method, _params, _deadline):
            if method == "thread/start":
                return {"thread": {"id": "test-thread"}}
            if method == "turn/start":
                bridge._calls["test-thread"].put(("answer", json.dumps(response())))
                bridge._calls["test-thread"].put(("done", "failed"))
                return {"turn": {"id": "test-turn"}}
            return {}
        with patch.object(bridge, "start"), patch.object(bridge, "_rpc", side_effect=rpc):
            with self.assertRaisesRegex(BridgeError, "inference_failed"):
                bridge.complete(model=QUICK, effort="high", system="Synthetic test", payload={},
                    schema=ultra.CHECKED_SCHEMA, deadline=time.monotonic()+TEST_WAIT_S, observer=lambda _: None)
        bridge._scratch = None

    def test_reasoning_and_unknown_events_never_reach_observers(self):
        bridge = CodexBridge(None)
        events = queue.Queue()
        bridge._calls["thread"] = events
        for method in ("item/reasoning/textDelta", "item/reasoning/summaryTextDelta", "turn/plan/updated", "warning"):
            bridge._dispatch({"method": method, "params": {"threadId": "thread", "delta": SECRET, "message": SECRET}}, None)
        bridge._dispatch({"method": "item/completed", "params": {"threadId": "thread", "item": {"type": "reasoning", "content": SECRET}}}, None)
        self.assertTrue(events.empty())
        bridge._dispatch({"method": "thread/tokenUsage/updated", "params": {"threadId": "thread", "tokenUsage": {
            "total": {"inputTokens": 9, "outputTokens": 4, "totalTokens": 13, "secret": SECRET}}}}, None)
        self.assertEqual(events.get_nowait(), ("usage", {"inputTokens": 9, "outputTokens": 4, "totalTokens": 13}))

    def test_approval_request_is_declined_and_reports_only_a_fixed_failure(self):
        bridge = CodexBridge(None)
        events = queue.Queue()
        bridge._calls["thread"] = events
        with patch.object(bridge, "_send") as send:
            bridge._dispatch({"id": 2, "method": "item/fileChange/requestApproval", "params": {"threadId": "thread", "reason": SECRET}}, None)
            self.assertEqual(send.call_args.args[0], {"id": 2, "result": {"decision": "decline"}})
        self.assertEqual(events.get_nowait(), ("blocked_action", None))

    def test_monitor_has_no_free_text_or_reasoning_fields(self):
        monitor = Monitor()
        monitor.begin()
        key = monitor.add("worker", QUICK)
        with self.assertRaises(ValueError):
            monitor.update(key, reasoning=SECRET)
        monitor.update(key, status="running", failure=SECRET)
        public = json.dumps(monitor.snapshot()) + table(monitor.snapshot())
        self.assertNotIn(SECRET, public)
        self.assertEqual(monitor.snapshot()["agents"][0]["failure"], "unavailable")
        self.assertIsNone(monitor.snapshot()["agents"][0]["total_tokens"])

    def test_crew_slot_is_fixed_and_effort_metadata_is_validated(self):
        monitor = Monitor()
        monitor.begin()
        key = monitor.add("worker", QUICK, effort="max", slot="worker-2")
        monitor.update(key, model=BRAIN, effort="medium", status="retrying")
        row = monitor.snapshot()["agents"][0]
        self.assertEqual((row["slot"], row["model"], row["effort"]), ("worker-2", BRAIN, "medium"))
        self.assertIn("medium", table(monitor.snapshot()))
        with self.assertRaises(ValueError):
            monitor.update(key, slot="worker-1")
        with self.assertRaises(ValueError):
            monitor.update(key, effort=SECRET)
        with self.assertRaises(ValueError):
            monitor.add("worker", QUICK, slot=SECRET)

    def test_browser_endpoint_is_local_only_and_does_not_serve_configuration(self):
        with patch.object(server.ultra.Settings, "read", return_value=(ultra.Settings(), None)):
            status, _, raw = request("/agents")
            self.assertEqual(status, 200)
            state = json.loads(raw)
            self.assertFalse(state["enabled"])
            self.assertEqual(state["agents"], [])
        self.assertEqual(request("/agents", headers={"Origin": "https://outside.example"})[0], 403)
        self.assertEqual(request("/ultra.json")[0], 404)
        self.assertEqual(request("/codex_bridge.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
