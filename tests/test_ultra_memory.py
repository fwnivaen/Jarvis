import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ultra_memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_explicit_preferences_persist_and_can_be_forgotten(self):
        path = self.root / "preferences.json"
        first = ultra_memory.Preferences(path)
        first.set("tone", "Concise")
        self.assertEqual(ultra_memory.Preferences(path).read(), {"tone": "Concise"})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(first.forget("tone")["forgotten"])
        self.assertEqual(first.read(), {})

    def test_credentials_corrupt_and_linked_storage_are_rejected(self):
        prefs = ultra_memory.Preferences(self.root / "prefs.json")
        for key in ("api_key", "password", "secret", "authorization"):
            with self.assertRaises(ValueError):
                prefs.set(key, "must not save")
        prefs.path.write_text("corrupt")
        self.assertEqual(prefs.read(), {})
        target = self.root / "target"
        target.write_text("untouched")
        prefs.path.unlink()
        prefs.path.symlink_to(target)
        with self.assertRaises(ValueError):
            prefs.set("tone", "short")
        self.assertEqual(target.read_text(), "untouched")

    def test_semantic_failure_keeps_keyword_retrieval(self):
        memory = ultra_memory.HybridMemory(self.root)
        notes = [{"id": 2, "label": "Budget", "text": "Budget is 120 pounds."}]
        with patch.object(memory, "_prepare", side_effect=RuntimeError("PRIVATE")):
            result = memory.search(notes, "budget")
        self.assertEqual(result[0]["id"], 2)
        self.assertEqual(memory.status()["notice"], "semantic_unavailable")
        self.assertNotIn("PRIVATE", str(memory.status()))

    def test_keyword_passages_are_verbatim(self):
        memory = ultra_memory.HybridMemory(self.root)
        text = "Nothing. " * 2000 + "Distinctive funding detail."
        result = memory.search([{"id": 1, "label": "Long note", "text": text}], "funding", semantic=False)
        self.assertIn("funding", result[0]["text"])
        self.assertIn(result[0]["text"], text)

    @unittest.skipUnless(os.environ.get("ULTRA_EMBEDDINGS_TEST") == "1", "explicit local model integration test")
    def test_real_semantic_synonyms_and_persistent_qdrant(self):
        notes = [{"id": 1, "label": "Rest", "text": "Sleep eight hours every night to recover."},
            {"id": 2, "label": "Plants", "text": "Tomatoes need water and sunlight."}]
        memory = ultra_memory.HybridMemory(self.root)
        try:
            found = memory.search(notes, "How can I improve my slumber?")
            self.assertTrue(memory.semantic_ready, memory.status())
            self.assertEqual(found[0]["id"], 1)
        finally:
            memory.close()
        reopened = ultra_memory.HybridMemory(self.root)
        try:
            self.assertEqual(reopened.search(notes, "slumber")[0]["id"], 1)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
