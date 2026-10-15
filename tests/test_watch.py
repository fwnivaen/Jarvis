import unittest
from unittest.mock import patch
import watch

class WatchTests(unittest.TestCase):
    def test_lease_privacy_and_independent_tabs(self):
        now = [0]
        w = watch.Watch(clock=lambda:now[0])
        with patch.object(watch, 'CARD') as card:
            card.is_file.return_value = False
            for token in ('first-test-session', 'second-test-session'):
                self.assertTrue(w.update(dict(token=token,active=True))['active'])
            self.assertTrue(w.update(dict(token='first-test-session',active=False))['active'])
            now[0] = watch.LEASE_S
            self.assertFalse(w.state()['active'])
            with self.assertRaises(ValueError):
                w.update(dict(token='second-test-session',active=True,image='forbidden'))
            with self.assertRaises(ValueError):
                w.update(dict(token='second-test-session',active=1))
