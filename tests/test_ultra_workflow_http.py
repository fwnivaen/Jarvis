"""Workflow HTTP integration: local metadata, explicit options and honest fallback."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import server
import ultra
from test_offline import TEST_CONFIG, request

ORIGIN = "http://127.0.0.1:4700"
QUESTION = "Compare the supplied notes."
RUN_ID = "a" * 24
ANSWER = {"answer": "Ready.", "about_notes": False, "nodes": []}


class WorkflowHttpTests(unittest.TestCase):
    def setUp(self):
        config = patch.object(server, "load_config", return_value=dict(TEST_CONFIG))
        config.start()
        self.addCleanup(config.stop)

    def test_workflow_metadata_uses_local_boundary(self):
        for path, method, value in (
                ("/agents/workflows", "workflow_catalog", {"enabled": True, "workflows": []}),
                ("/agents/runs", "run_summaries", {"enabled": True, "runs": []})):
            with self.subTest(path=path), patch.object(server.ULTRA, method, return_value=value) as getter:
                status, _, raw = request(path)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw), value)
                getter.assert_called_once()
                getter.reset_mock()
                self.assertEqual(request(path, headers={"Origin": "https://outside.example"})[0], 403)
                getter.assert_not_called()
        self.assertEqual(request("/.local/ultra-runs/" + RUN_ID + ".json")[0], 404)

    def test_options_reach_runtime_without_altering_question(self):
        settings = replace(ultra.Settings(), enabled=True)
        with patch.object(server.ultra.Settings, "read", return_value=(settings, None)), \
                patch.object(server, "ACTIVE_BRAIN", None), \
                patch.object(server.ULTRA, "answer", return_value=ANSWER) as answer:
            result = server.answer_request("system", [], [], QUESTION, workflow="research", resume_run=RUN_ID)
            self.assertEqual(result, ANSWER)
            self.assertEqual(answer.call_args.kwargs["workflow"], "research")
            self.assertEqual(answer.call_args.kwargs["resume_run"], RUN_ID)

    def test_disabled_or_manual_route_does_not_silently_restart(self):
        for settings, manual in ((ultra.Settings(), None),
                (replace(ultra.Settings(), enabled=True), ("codex-cli", "gpt-6-astra"))):
            with self.subTest(manual=manual), \
                    patch.object(server.ultra.Settings, "read", return_value=(settings, None)), \
                    patch.object(server, "ACTIVE_BRAIN", manual), \
                    patch.object(server, "ask_brain") as legacy, \
                    patch.object(server.ULTRA, "answer") as runtime:
                self.assertTrue(server.answer_request("system", [], [], QUESTION, resume_run=RUN_ID)["error"])
                legacy.assert_not_called()
                runtime.assert_not_called()

    def test_chat_passes_explicit_options_and_validates_types(self):
        posture = dict(eyes_active=False, present=False, head_down=False, slouched=False)
        with patch.object(server.build, "NOTES_DIR", Path(__file__).parent), \
                patch.object(server, "retrieve", return_value=[]), \
                patch.object(server.FOCUS, "state", return_value=posture), \
                patch.object(server, "answer_request", return_value=ANSWER) as answer:
            status, _, _ = request("/chat", "POST", dict(question=QUESTION, workflow="research", resume_run=RUN_ID))
            self.assertEqual(status, 200)
            self.assertEqual(answer.call_args.kwargs, {"workflow": "research", "resume_run": RUN_ID})
            for field, value in (("workflow", True), ("resume_run", []), ("workflow", " research"),
                    ("resume_run", "x" * (server.MAX_RESUME_RUN_CHARS + 1))):
                self.assertEqual(request("/chat", "POST", {"question": QUESTION, field: value})[0], 400)
        self.assertEqual(request("/remember", "POST", dict(question=QUESTION, workflow="research"))[0], 400)


if __name__ == "__main__":
    unittest.main()
