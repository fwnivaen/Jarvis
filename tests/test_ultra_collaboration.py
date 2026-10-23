"""Crew contracts: parallel drafts, shared evidence, one review and bounded recovery."""
import json
import tempfile
import threading
import time
import unittest
import functools
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

import ultra
from ultra_workflows import WorkflowStore
from test_ultra import FakeBridge, NOTES, response
import ultra_tools


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = WorkflowStore(Path(self.temporary.name) / "runs")
        self.settings = replace(ultra.Settings(), enabled=True, terminal_monitor_enabled=False)

    def run_crew(self, handler, **options):
        bridge = FakeBridge(handler)
        runtime = ultra.UltraJarvis(lambda: bridge, workflow_store=self.store)
        result = runtime.answer(self.settings, "Read supplied data.", NOTES, [],
            "Use three workers to compare the budget.", **options)
        return result, bridge, runtime

    def handler(self, call):
        if "tasks" in call["schema"]["properties"]:
            return {"tasks": [{"task": "Inspect part " + str(n), "kind": "general"} for n in range(3)]}
        if "assignment" in call["payload"]:
            return dict(response(note=True), unresolved_issues=[])
        return response("Boss checked the budget.", note=True)

    def test_three_workers_share_evidence_then_boss_synthesizes(self):
        barriers = {False: threading.Barrier(3), True: threading.Barrier(3)}
        def handle(call):
            if "assignment" in call["payload"]:
                reviewing = "peer_reports" in call["payload"]
                barriers[reviewing].wait(timeout=2)
                if reviewing:
                    self.assertGreaterEqual(len(call["payload"]["peer_reports"]), 1)
                    self.assertLessEqual(len(call["payload"]["peer_reports"]), 2)
                    self.assertTrue(all(p["evidence"] for p in call["payload"]["peer_reports"]))
            return self.handler(call)
        value, bridge, runtime = self.run_crew(handle)
        self.assertFalse(value.get("error"), value)
        workers = [call for call in bridge.calls if "assignment" in call["payload"]]
        self.assertEqual(len(workers), 6)
        for model, effort in ultra.CREW_PROFILES:
            pair = [c for c in workers if (c["model"], c["effort"]) == (model, effort)]
            self.assertEqual(len(pair), 2)
            self.assertEqual(pair[0]["deadline"], pair[1]["deadline"])
        self.assertEqual(bridge.calls[-1]["effort"], "max")
        self.assertEqual(len(bridge.calls[-1]["payload"]["worker_results"]), 3)
        rows = runtime.monitor.snapshot()["agents"]
        self.assertTrue(all(r["total_tokens"] == 28 for r in rows if r["role"] == "worker"))
        self.assertEqual(value["ultra"]["evaluation"]["total_tokens"], 112)
        self.assertTrue(value["ultra"]["run_id"])

    def test_collaboration_flag_removes_review_calls(self):
        self.settings = replace(self.settings, collaboration_enabled=False)
        value, bridge, _ = self.run_crew(self.handler)
        self.assertFalse(value.get("error"), value)
        self.assertEqual(sum("assignment" in c["payload"] for c in bridge.calls), 3)

    def test_slow_draft_does_not_block_other_workers_peer_review(self):
        reviewing = threading.Event()
        lock = threading.Lock()
        active, peak = [0], [0]
        def handle(call):
            if "assignment" not in call["payload"]:
                return self.handler(call)
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            try:
                if "peer_reports" in call["payload"]:
                    reviewing.set()
                elif call["payload"]["assignment"] == "Inspect part 1":
                    self.assertTrue(reviewing.wait(timeout=2), "A slow draft blocked all peer review")
                return self.handler(call)
            finally:
                with lock:
                    active[0] -= 1
        value, _, _ = self.run_crew(handle)
        self.assertFalse(value.get("partial"), value)
        self.assertLessEqual(peak[0], 3)

    def test_complete_checkpoint_returns_validated_answer_without_model(self):
        value, bridge, runtime = self.run_crew(self.handler)
        before = len(bridge.calls)
        rows = runtime.monitor.snapshot()["agents"]
        recovered = runtime.answer(self.settings, "Read supplied data.", NOTES, [],
            "Use three workers to compare the budget.", resume_run=value["ultra"]["run_id"])
        self.assertEqual(recovered["answer"], value["answer"])
        self.assertEqual(len(bridge.calls), before)
        self.assertEqual(recovered["ultra"]["evaluation"], value["ultra"]["evaluation"])
        restored = runtime.monitor.snapshot()["agents"]
        fields = ("role", "slot", "model", "effort", "status", "failure", "retries", "total_tokens", "elapsed_s")
        self.assertEqual([{key: row[key] for key in fields} for row in restored],
                         [{key: row[key] for key in fields} for row in rows])

    def test_saved_reports_resume_only_boss_and_preserve_all_token_use(self):
        value, bridge, runtime = self.run_crew(self.handler)
        run_id = value["ultra"]["run_id"]
        state = self.store.load(run_id)
        state.update(status="interrupted", final=None)
        self.store.save(run_id, runtime._fingerprint, state)
        before = len(bridge.calls)
        recovered = runtime.answer(self.settings, "Read supplied data.", NOTES, [],
            "Use three workers to compare the budget.", resume_run=run_id)
        self.assertFalse(recovered.get("error"), recovered)
        self.assertEqual(len(bridge.calls), before + 1)
        self.assertEqual(recovered["ultra"]["evaluation"]["total_tokens"], 126)
        self.assertEqual(sum(row["role"] == "worker" for row in runtime.monitor.snapshot()["agents"]), 3)

    def test_boss_timeout_returns_clearly_labelled_verified_worker_findings(self):
        def handle(call):
            if "worker_results" in call["payload"]:
                raise ultra.BridgeError("timeout")
            return self.handler(call)
        value, _, _ = self.run_crew(handle)
        self.assertTrue(value["partial"])
        self.assertTrue(value["review_incomplete"])
        self.assertIn("have not received a final boss review", value["answer"])
        self.assertEqual(value["nodes"], [7])

    def test_tool_sources_are_given_to_boss_without_repeating_tools(self):
        found = {"id": 9, "title": "New source", "text": "The opening time is nine.", "revision": "r1"}
        registry = ultra_tools.Registry(lambda: self.settings, {"notes_search": lambda query: {"notes": [found]}})
        def handle(call):
            if "tasks" in call["schema"]["properties"]:
                return {"tasks": [{"task": "Find opening time", "kind": "general"}]}
            if "assignment" in call["payload"]:
                call["tool_handler"]("notes_search", {"query": "opening time"}, call["deadline"])
            else:
                self.assertIn(found, call["payload"]["notes"])
                self.assertNotIn("tools", call)
            return dict(answer="Opening time is nine.", about_notes=True, nodes=[9],
                evidence=[{"node": 9, "quote": found["text"]}], calculations=[],
                **({"unresolved_issues": []} if "assignment" in call["payload"] else {}))
        bridge = FakeBridge(handle)
        runtime = ultra.UltraJarvis(lambda: bridge, workflow_store=self.store)
        runtime.tool_layer = registry
        original_session = ultra_tools.ToolSession
        with patch.object(ultra_tools, "ToolSession", functools.partial(original_session, root=Path(self.temporary.name) / "tools")):
            value = runtime.answer(self.settings, "Test", NOTES, [], "Use workers to find the opening time.")
        self.assertFalse(value.get("error"), value)
        self.assertEqual(value["nodes"], [9])

    def test_mismatched_question_does_not_replay_or_modify_run(self):
        value, bridge, runtime = self.run_crew(self.handler)
        run_id = value["ultra"]["run_id"]
        before = self.store.load(run_id)
        count = len(bridge.calls)
        rejected = runtime.answer(self.settings, "Read supplied data.", NOTES, [], "Different", resume_run=run_id)
        self.assertTrue(rejected["error"])
        self.assertEqual(len(bridge.calls), count)
        self.assertEqual(self.store.load(run_id), before)

    def test_reviewed_partial_answer_is_read_back_without_restarting_workers(self):
        self.settings = replace(self.settings, worker_retries=0)
        def handle(call):
            if call["payload"].get("assignment") == "Inspect part 1":
                raise ultra.BridgeError("inference_failed")
            return self.handler(call)
        value, bridge, runtime = self.run_crew(handle)
        self.assertTrue(value["partial"])
        self.assertFalse(value["ultra"]["resumable"])
        workers = [row for row in runtime.monitor.snapshot()["agents"] if row["role"] == "worker"]
        count = len(bridge.calls)
        cached = runtime.answer(self.settings, "Read supplied data.", NOTES, [],
            "Use three workers to compare the budget.", resume_run=value["ultra"]["run_id"])
        self.assertEqual(cached["answer"], value["answer"])
        self.assertTrue(cached["partial"])
        self.assertEqual(len(bridge.calls), count)
        restored = [row for row in runtime.monitor.snapshot()["agents"] if row["role"] == "worker"]
        self.assertEqual([row["status"] for row in restored], [row["status"] for row in workers])
        self.assertEqual(sum(row["status"] == "failed" for row in restored), 1)

    def test_expired_incomplete_run_cannot_reset_budget(self):
        value, bridge, runtime = self.run_crew(self.handler)
        run_id = value["ultra"]["run_id"]
        state = self.store.load(run_id)
        state.update(status="interrupted", final=None)
        state["budget"]["request_expires_at"] = time.time() - 1
        self.store.save(run_id, runtime._fingerprint, state)
        count = len(bridge.calls)
        rejected = runtime.answer(self.settings, "Read supplied data.", NOTES, [],
            "Use three workers to compare the budget.", resume_run=run_id)
        self.assertTrue(rejected["error"])
        self.assertIn("time budget", rejected["answer"])
        self.assertEqual(len(bridge.calls), count)

    def test_shared_retry_budget_not_reset_for_peer_review(self):
        calls = {}
        def handle(call):
            if "assignment" in call["payload"]:
                key = call["payload"]["assignment"]
                calls[key] = calls.get(key, 0) + 1
                if calls[key] == 1 or "peer_reports" in call["payload"]:
                    return "invalid json"
            return self.handler(call)
        value, _, runtime = self.run_crew(handle)
        self.assertTrue(value.get("partial"), value)
        self.assertTrue(all(count == 4 for count in calls.values()))
        self.assertTrue(all(row["retries"] == 2 for row in runtime.monitor.snapshot()["agents"] if row["role"] == "worker"))
        self.assertEqual(value["ultra"]["escalations"], 1)


if __name__ == "__main__":
    unittest.main()
