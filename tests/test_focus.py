"""Deterministic privacy and accounting checks, without macOS access or speech."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from focus import Focus, PUBLIC_KEYS, LEDGER_KEYS, parse_command
from focus_reader import Reader, FRONT_SCRIPT


class Clock:
    value = 0.0
    def __call__(self):
        return self.value


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.bundle = 'com.google.Chrome'
        self.url = 'https://private-work.example/customer/SECRET?token=SECRET#SECRET'
        self.queries = []
        def query(script):
            self.queries.append(script)
            if self.bundle is None:
                raise OSError('private diagnostic')
            return self.bundle if script == FRONT_SCRIPT else self.url
        self.reader = Reader(query)
        self.speech = []
        self.path = Path(self.temp.name) / 'ledger.json'
        self.focus = Focus(self.reader, self.clock, self.speech.append, self.path)

    def tick(self, seconds=1):
        self.clock.value += seconds
        self.focus.tick()

    def assert_private(self):
        state = self.focus.state()
        self.assertEqual(set(state), PUBLIC_KEYS)
        self.assertTrue(all(type(v) in (bool, int, float) for v in state.values()))
        encoded = json.dumps(state)
        for identity in ('com.google.Chrome', 'private-work', 'SECRET', 'evil.example', 'sha256'):
            self.assertNotIn(identity, encoded)
        self.assertEqual(set(self.reader.sample()), {'known', 'home', 'target', 'locked'})

    def test_reader_fresh_host_only_and_home(self):
        self.focus.command('start', 100)
        self.url = 'https://private-work.example/different/path?other=secret'
        self.tick()
        self.assertFalse(self.focus.state()['drifting'])
        self.assertEqual(self.queries.count(FRONT_SCRIPT), 2)
        self.url = 'https://evil.example/'
        self.tick()
        self.assertEqual(len(self.speech), 0)
        self.tick()
        self.assertEqual(len(self.speech), 1)
        self.assert_private()
        self.url = 'http://localhost:4700/?mute=1'
        self.tick(40)
        self.assertTrue(self.focus.state()['home'])
        self.assertEqual(len(self.speech), 1)
        self.focus.command('excuse')
        self.assertEqual(self.focus.state()['drifts'], 0)
        self.assertEqual(self.focus.state()['drift_s'], 0)
        self.url = 'https://evil.example/'
        self.tick(40)
        self.assertEqual(len(self.speech), 1)
        self.url = 'https://private-work.example/back'
        self.tick()
        self.assertFalse(self.focus.state()['excused'])

    def test_reload_is_read_only_and_privacy_all_states(self):
        self.url = 'http://127.0.0.1:4700/'
        self.focus.command('start', 100)
        self.assertTrue(self.focus.state()['armed'])
        self.assert_private()
        self.tick(10)
        self.assertEqual(self.focus.state()['remaining_s'], 100)
        self.url = 'https://private-work.example/task'
        self.tick()
        for _ in range(5):
            self.assert_private()  # Reloads/polls cannot advance or reset a session.
        self.assertEqual(self.focus.state()['remaining_s'], 100)
        self.tick()
        self.bundle = 'org.secret.OtherApp'
        self.tick()
        self.tick()
        for command, seconds in [('pause', None), ('resume', None), ('snooze', 15), ('nag', 30), ('excuse', None), ('extend', 60), ('end', None)]:
            self.focus.command(command, seconds)
            self.assert_private()
        ledger = json.loads(self.path.read_text())
        self.assertEqual(set(ledger), set(LEDGER_KEYS))
        self.assertTrue(all(type(v) in (int, float) for v in ledger.values()))
        self.assertIsNone(self.reader._target)

    def test_pause_nag_snooze_tiers_return_and_abort(self):
        self.focus.command('start', 500)
        self.focus.command('nag', 3)
        self.bundle = 'org.other.app'
        self.tick()
        self.tick()
        self.assertEqual(self.focus.state()['tier'], 1)
        self.focus.command('snooze', 15)
        self.tick(14)
        self.assertEqual(len(self.speech), 1)
        self.tick()
        self.assertEqual(self.focus.state()['tier'], 2)
        self.tick(3)
        self.assertEqual(self.focus.state()['tier'], 3)
        self.assertEqual(self.focus.state()['drifts'], 1)
        self.focus.command('pause')
        before = self.focus.state()['remaining_s']
        self.tick(50)
        self.assertEqual(self.focus.state()['remaining_s'], before)
        self.focus.command('resume')
        self.bundle = 'com.google.Chrome'
        self.tick()
        self.assertFalse(self.focus.state()['drifting'])
        self.focus.command('abort')
        self.assertTrue(self.focus.state()['aborted'])
        self.assertIn('Aborted', self.speech[-1])
        self.assertEqual(self.focus.state()['streak'], 0)

    def test_unavailable_does_not_claim_focus(self):
        self.focus.command('start', 100)
        self.bundle = None
        self.tick(50)
        self.assertFalse(self.focus.state()['known'])
        self.assertEqual(self.focus.state()['elapsed_s'], 0)
        self.assertEqual(self.speech, [])

    def test_clean_streak_persisted_early_end_does_not_earn_it(self):
        self.focus.command('start', 10)
        self.tick(10)
        self.assertTrue(self.focus.state()['completed'])
        self.assertEqual(self.focus.state()['streak'], 1)
        restored = Focus(self.reader, self.clock, self.speech.append, self.path)
        self.assertEqual(restored.state()['streak'], 1)
        restored.command('start', 100)
        restored.command('end')
        self.assertEqual(restored.state()['streak'], 0)
        self.assertIn('minutes on target out of', self.speech[-1])

    def test_grace_refunded_and_bad_values(self):
        self.focus.command('start', 20)
        self.bundle = 'other'
        self.tick()
        self.bundle = 'com.google.Chrome'
        self.tick(0.5)
        self.assertEqual(self.focus.state()['drifts'], 0)
        self.assertEqual(self.focus.state()['drift_s'], 0)
        for value in (float('nan'), float('inf'), -1, True, '30'):
            with self.assertRaises(ValueError):
                self.focus.command('extend', value)

    def test_http_state_privacy_origin_and_reload(self):
        from unittest.mock import patch
        from test_offline import request
        import server
        with patch.object(server, 'FOCUS', self.focus):
            denied, _, _ = request('/focus', 'POST', {'action': 'start'})
            self.assertEqual(denied, 403)
            status, _, body = request('/focus', 'POST', {'question': 'thirty minutes on this'},
                                     {'Origin': 'http://127.0.0.1:4700'})
            self.assertEqual(status, 200)
            self.assertEqual(set(json.loads(body)['state']), PUBLIC_KEYS)
            self.tick(2)
            for _ in range(2):
                status, _, body = request('/focus')
                state = json.loads(body)
                self.assertEqual(status, 200)
                self.assertEqual(set(state), PUBLIC_KEYS)
                self.assertTrue(all(type(v) in (bool, int, float) for v in state.values()))
                self.assertEqual(state['remaining_s'], 1798)
            self.assert_private()

    def test_internal_browser_pages_are_drift_not_permission_failure(self):
        self.focus.command('start', 30)
        for url in ('chrome://newtab/', 'about:blank', 'file:///private/test.html'):
            self.url = url
            self.tick()
            self.tick()
            self.assertTrue(self.focus.state()['known'])
            self.assertTrue(self.focus.state()['drifting'])

    def test_voice_grammar(self):
        for text, expected in [
            ('thirty minutes on this', ('start', 1800)),
            ('Jarvis, call me out every thirty seconds', ('nag', 30)),
            ('give me fifteen seconds', ('snooze', 15)),
            ("it's okay, I'm doing research", ('excuse', None)),
            ('extend by five minutes', ('extend', 300)),
            ('twenty five minutes on this', ('start', 1500)),
            ('pause', ('pause', None)), ('resume', ('resume', None)),
            ('abort', ('abort', None)), ('end the session', ('end', None))]:
            self.assertEqual(parse_command(text), expected, text)
        self.assertIsNone(parse_command('What does menu pricing say?'))


if __name__ == '__main__':
    unittest.main()
