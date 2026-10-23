"""Metadata-only collaboration events and worker lifecycle regression checks."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ultra_monitor import EVENTS, MAX_EVENTS, Monitor, table

MODEL = "gpt-6-luna"
SECRET = "PRIVATE_REPORT_SOURCE_ARGUMENTS_AND_REASONING"
INITIAL_TIME = 100
COMPLETED_AFTER = 3
REVIEW_AFTER = 5
SNAPSHOT_AFTER = 7
EXCESS_EVENTS = 4


class CollaborationMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = INITIAL_TIME
        self.monitor = Monitor(clock=lambda: self.now)
        self.monitor.begin()

    def test_restarting_worker_review_unfreezes_total_elapsed(self):
        key = self.monitor.add("worker", MODEL, slot="worker-2")
        self.monitor.update(key, status="running", phase="drafting")
        self.now += COMPLETED_AFTER
        self.monitor.update(key, status="complete")
        self.assertEqual(self.monitor.snapshot()["agents"][0]["elapsed_s"], COMPLETED_AFTER)
        self.now = INITIAL_TIME + REVIEW_AFTER
        self.monitor.update(key, status="running", phase="reviewing")
        self.now = INITIAL_TIME + SNAPSHOT_AFTER
        row = self.monitor.snapshot()["agents"][0]
        self.assertEqual(row["elapsed_s"], SNAPSHOT_AFTER)
        self.assertEqual(row["phase"], "reviewing")
        self.assertIn("reviewing", table(self.monitor.snapshot()))
        self.assertEqual(len(self.monitor.snapshot()["agents"]), 1)

    def test_queued_or_retrying_also_reopens_a_completed_row(self):
        for status in ("queued", "retrying"):
            key = self.monitor.add("worker", MODEL)
            self.monitor.update(key, status="complete")
            self.monitor.update(key, status=status)
            self.now += COMPLETED_AFTER
            self.assertGreater(self.monitor.snapshot()["agents"][-1]["elapsed_s"], 0)

    def test_safe_events_are_bounded_and_reset_for_each_request(self):
        for index in range(MAX_EVENTS + EXCESS_EVENTS):
            self.now = INITIAL_TIME + index
            self.monitor.event("checkpoint_saved", slot="worker-1")
        events = self.monitor.snapshot()["events"]
        self.assertEqual(len(events), MAX_EVENTS)
        self.assertEqual(events[0]["elapsed_s"], EXCESS_EVENTS)
        self.assertEqual(set(events[0]), {"kind", "slot", "elapsed_s"})
        events[0]["kind"] = SECRET
        self.assertNotIn(SECRET, json.dumps(self.monitor.snapshot()))
        self.monitor.begin()
        self.assertEqual(self.monitor.snapshot()["events"], [])

    def test_events_never_accept_free_text_or_out_of_range_slots(self):
        for kind in EVENTS:
            self.monitor.event(kind)
        for value in (SECRET, "", "worker-0", "worker-17", "worker-01", "boss\n" + SECRET, [], {}, False):
            with self.assertRaises(ValueError):
                self.monitor.event(value)
            with self.assertRaises(ValueError):
                self.monitor.event("reported", slot=value)
        with self.assertRaises(TypeError):
            self.monitor.event("reported", report=SECRET)
        self.assertNotIn(SECRET, json.dumps(self.monitor.snapshot()) + table(self.monitor.snapshot()))


if __name__ == "__main__":
    unittest.main()
