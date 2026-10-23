"""Offline workflow selection, recovery boundaries and private storage checks."""
import copy
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ultra_workflows as workflows

SENTINEL = "PRIVATE_CONVERSATION_SENTINEL"
MODEL = "test-model"
RUN_BYTES_LIMIT = 300
LIST_LIMIT = 1


def context():
    return {"question": "Summarize my notes", "notes": [{"id": 1, "text": "A source"}],
        "history": [], "profiles": [{"model": MODEL, "effort": "high"}],
        "flags": {"collaboration_enabled": True}}


def state():
    return {"status": "interrupted", "workflow": "research", "phase": "workers",
        "context": {"history": [{"role": "user", "content": SENTINEL}], "workflow": "research"},
        "plan": [{"task": "Read the source", "kind": "general"}],
        "reports": [{"answer": SENTINEL, "sources": [1], "status": "complete"}],
        "budget": {"request_remaining_s": 120, "escalation_remaining": 0, "escalations": 1},
        "worker_state": [{"model": MODEL, "effort": "high", "retries": 2,
            "escalated": True, "tokens": {"total_tokens": 100}, "remaining_s": 5, "status": "complete"}]}


class WorkflowRecipeTests(unittest.TestCase):
    def test_explicit_workflow_has_precedence_and_roles_are_independent_copies(self):
        template = workflows.workflow_template("code", "research")
        self.assertEqual(template["id"], "research")
        self.assertEqual(len(template["roles"]), workflows.ROLE_COUNT)
        template["roles"][0]["name"] = "Changed"
        self.assertNotEqual(workflows.workflow_template(workflow="research")["roles"][0]["name"], "Changed")
        self.assertEqual(workflows.workflow_template("code")["id"], "code")
        self.assertEqual(workflows.workflow_template("computer")["id"], "general")
        with self.assertRaises(ValueError):
            workflows.workflow_template(workflow="do anything")

    def test_catalog_contains_all_four_templates_without_run_content(self):
        catalog = workflows.workflow_templates()
        self.assertEqual({item["id"] for item in catalog}, {"general", "research", "code", "document"})
        self.assertTrue(all(item["criteria"] for item in catalog))

    def test_fingerprint_is_order_independent_and_invalidates_relevant_context(self):
        original = context()
        fingerprint = workflows.context_fingerprint(original)
        self.assertEqual(workflows.context_fingerprint(dict(reversed(list(original.items())))), fingerprint)
        variants = []
        for key, replacement in (("question", "Different question"), ("notes", [{"id": 1, "text": "Updated source"}]),
                ("history", ["Earlier context"]), ("profiles", [{"model": MODEL, "effort": "max"}]),
                ("flags", {"collaboration_enabled": False})):
            changed = copy.deepcopy(original)
            changed[key] = replacement
            variants.append(workflows.context_fingerprint(changed))
        self.assertTrue(all(item != fingerprint for item in variants))
        self.assertEqual(len(fingerprint), len(workflows.context_fingerprint({})))


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "runs"
        self.store = workflows.WorkflowStore(self.root, clock=lambda: 100)
        self.fingerprint = workflows.context_fingerprint(context())

    def tearDown(self):
        self.directory.cleanup()

    def test_round_trip_preserves_completed_reports_and_consumed_budgets(self):
        original = state()
        run_id = self.store.start(self.fingerprint, original)
        self.assertRegex(run_id, workflows.RUN_ID)
        loaded = self.store.load(run_id, self.fingerprint)
        self.assertEqual(loaded, original)
        self.assertEqual(loaded["budget"]["escalation_remaining"], 0)
        self.assertEqual(loaded["worker_state"][0]["retries"], 2)
        self.assertEqual(loaded["worker_state"][0]["remaining_s"], 5)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), workflows.PRIVATE_DIRECTORY_MODE)
        self.assertEqual(stat.S_IMODE((self.root / (run_id + ".json")).stat().st_mode), workflows.PRIVATE_FILE_MODE)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_context_mismatch_fails_closed_and_does_not_overwrite_original(self):
        run_id = self.store.start(self.fingerprint, state())
        other = workflows.context_fingerprint({"question": "Different"})
        self.assertIsNone(self.store.load(run_id, other))
        self.assertFalse(self.store.save(run_id, other, {"status": "complete"}))
        self.assertEqual(self.store.load(run_id, self.fingerprint), state())

    def test_safe_list_does_not_expose_context_reports_or_fingerprint(self):
        stored = state()
        stored["metrics"] = {"status": "partial", "jobs": 3, "total_tokens": 100,
            "answer": SENTINEL, "retries": 2}
        run_id = self.store.start(self.fingerprint, stored)
        listing = self.store.list_runs()
        self.assertEqual(listing[0]["run_id"], run_id)
        self.assertEqual(listing[0]["evaluation"], {"status": "partial", "jobs": 3,
            "retries": 2, "total_tokens": 100})
        self.assertNotIn(SENTINEL, json.dumps(listing))
        self.assertNotIn(self.fingerprint, json.dumps(listing))
        self.assertNotIn("context", listing[0])

    def test_corrupt_truncated_unknown_and_oversized_files_are_skipped(self):
        run_id = self.store.start(self.fingerprint, state())
        target = self.root / (run_id + ".json")
        original = target.read_bytes()
        for invalid in (b"{", b"[]", b'{"version":1}', b"x" * RUN_BYTES_LIMIT):
            target.write_bytes(invalid)
            with patch.object(workflows, "MAX_RUN_BYTES", RUN_BYTES_LIMIT):
                self.assertIsNone(self.store.load(run_id, self.fingerprint))
                self.assertEqual(self.store.list_runs(), [])
        target.write_bytes(original)
        self.assertEqual(self.store.load(run_id, self.fingerprint), state())

    def test_atomic_write_failure_preserves_previous_checkpoint_and_cleans_temp(self):
        run_id = self.store.start(self.fingerprint, state())
        original = (self.root / (run_id + ".json")).read_bytes()
        with patch.object(workflows.os, "replace", side_effect=OSError("Interrupted write")):
            self.assertFalse(self.store.save(run_id, self.fingerprint, {"status": "complete"}))
        self.assertEqual((self.root / (run_id + ".json")).read_bytes(), original)
        self.assertFalse(any(item.suffix == ".tmp" for item in self.root.iterdir()))

    def test_invalid_ids_symlink_root_and_symlink_files_fail_closed(self):
        for run_id in ("../outside", "A" * 24, "f" * 25, None):
            self.assertIsNone(self.store.load(run_id))
            self.assertFalse(self.store.save(run_id, self.fingerprint, state()))
        outside = Path(self.directory.name) / "outside"
        outside.mkdir()
        self.root.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(self.store.start(self.fingerprint, state()))
        self.assertEqual(list(outside.iterdir()), [])
        self.root.unlink()
        self.root.mkdir()
        target = outside / "target.json"
        target.write_text(SENTINEL)
        run_id = "a" * 24
        (self.root / (run_id + ".json")).symlink_to(target)
        self.assertIsNone(self.store.load(run_id))
        self.assertFalse(self.store.save(run_id, self.fingerprint, state()))
        self.assertEqual(target.read_text(), SENTINEL)

    def test_hardlinked_file_and_nonregular_checkpoint_are_rejected(self):
        run_id = self.store.start(self.fingerprint, state())
        target = self.root / (run_id + ".json")
        os.link(target, Path(self.directory.name) / "hardlink.json")
        self.assertIsNone(self.store.load(run_id))
        target.unlink()
        target.mkdir()
        self.assertIsNone(self.store.load(run_id))

    def test_file_permissions_are_repaired_on_read(self):
        run_id = self.store.start(self.fingerprint, state())
        target = self.root / (run_id + ".json")
        self.root.chmod(0o755)
        target.chmod(0o644)
        self.assertEqual(self.store.load(run_id), state())
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), workflows.PRIVATE_DIRECTORY_MODE)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), workflows.PRIVATE_FILE_MODE)

    def test_caps_and_invalid_state_do_not_create_unbounded_or_secret_storage(self):
        for invalid in ({"question": SENTINEL}, {"reports": [{"reasoning": SENTINEL}]},
                {"context": {"notes": SENTINEL}}, {"budget": {"remaining": float("nan")}},
                {"status": "arbitrary"}, {"workflow": "unknown"}):
            self.assertIsNone(self.store.start(self.fingerprint, invalid))
        with patch.object(workflows, "MAX_RUNS", LIST_LIMIT):
            self.assertIsNotNone(self.store.start(self.fingerprint, state()))
            self.assertIsNone(self.store.start(self.fingerprint, state()))
        with patch.object(workflows, "MAX_RUN_BYTES", RUN_BYTES_LIMIT):
            self.assertIsNone(self.store.start(self.fingerprint, state()))
        self.assertEqual(self.store.list_runs(limit=0), [])


class EvaluationTests(unittest.TestCase):
    def test_evaluation_reports_observed_numbers_without_text_or_judge(self):
        snapshot = {"elapsed_s": 12.3456, "escalations": 1, "agents": [
            {"role": "worker", "slot": "worker-1", "status": "complete", "retries": 1,
                "input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "answer": SENTINEL},
            {"role": "worker", "slot": "worker-1", "status": "complete", "retries": 0,
                "input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
            {"role": "worker", "slot": "worker-2", "status": "failed", "retries": 2}]}
        summary = workflows.evaluation_summary(snapshot, {"answer": SENTINEL, "partial": True},
            [{"name": "sources", "status": "passed"}, {"name": "math", "status": "failed"}])
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["workers"], 2)
        self.assertEqual(summary["jobs"], 3)
        self.assertEqual(summary["total_tokens"], 40)
        self.assertFalse(summary["token_usage_complete"])
        self.assertEqual(summary["retries"], 3)
        self.assertEqual(summary["checks_passed"], 1)
        self.assertEqual(summary["checks_failed"], 1)
        self.assertNotIn(SENTINEL, json.dumps(summary))
        self.assertEqual(workflows.evaluation_summary({}, {"error": True})["status"], "failed")
        self.assertIsNone(workflows.evaluation_summary({})["total_tokens"])


if __name__ == "__main__":
    unittest.main()
