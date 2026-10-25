"""Command admission, replay protection, partial results and HTTP permission boundaries."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import assistant_actions as actions
import sensor_state
import server
from test_offline import request

ORIGIN = {'Origin': 'http://127.0.0.1:4700'}
KEY = 'ab' * 12


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.runner = Mock(return_value=SimpleNamespace(returncode=0))
        self.path = Path(self.scratch.name) / 'state.json'
        self.assistant = actions.Assistant(self.path, self.runner)
        self.apps = patch.object(actions, 'installed_apps', return_value={'safari': Path('/Applications/Safari.app'), 'notes': Path('/System/Applications/Notes.app')})
        self.apps.start(); self.addCleanup(self.apps.stop)

    def run_command(self, text, key=KEY):
        return self.assistant.execute(text, key)

    def test_ordinary_question_never_calls_a_command(self):
        self.assertEqual(self.run_command('Who wrote the supplier notes?'), {'matched': False})
        self.runner.assert_not_called()

    def test_untrusted_shell_and_non_web_urls_never_execute(self):
        for text in ('rm -rf ~/Documents', 'open $(touch /tmp/pwn)', 'open file:///etc/passwd', 'open https://user:secret@example.com', 'launch Safari; sudo reboot'):
            try:
                value = self.run_command(text)
                self.assertFalse(value['matched'])
            except actions.CommandError:
                pass
        self.runner.assert_not_called()

    def test_app_and_search_are_argument_arrays_and_honest_requests(self):
        value = self.run_command('Open Safari')
        self.assertIn('requested', value['answer'])
        self.assertEqual(self.runner.call_args.args[0], ['/usr/bin/open', '-a', '/Applications/Safari.app'])
        self.run_command('Search the web for a & b', 'cd'*12)
        self.assertEqual(self.runner.call_args.args[0][-1], 'https://www.google.com/search?q=a+%26+b')
        self.assertNotIn('shell', self.runner.call_args.kwargs)

    def test_teaching_is_explicit_and_does_not_execute(self):
        self.run_command('When I say writing time, open Notes and then open Safari')
        self.runner.assert_not_called()
        restored = actions.Assistant(self.path, self.runner)
        result = restored.execute('Writing time!', 'cd'*12)
        self.assertFalse(result.get('error'))
        self.assertEqual(self.runner.call_count, 2)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_routines_cannot_shadow_builtins_or_contain_arbitrary_work(self):
        for text in ('When I say open Safari, open Notes', 'When I say draft email, send an email', 'When I say hi, open Safari; rm test'):
            with self.assertRaises(actions.CommandError):
                self.run_command(text)
        self.runner.assert_not_called()

    def test_repeated_key_cannot_repeat_side_effects_even_after_restart(self):
        original = self.run_command('Open Safari')
        again = actions.Assistant(self.path, self.runner).execute('Open Safari', KEY)
        self.assertEqual(original, again)
        self.runner.assert_called_once()
        with self.assertRaises(actions.CommandError):
            self.run_command('Open Notes')

    def test_partial_routine_stops_and_never_replays_completed_steps(self):
        self.run_command('When I say writing time, open Notes and then open Safari')
        self.runner.side_effect = [SimpleNamespace(returncode=0), subprocess.TimeoutExpired('open', 8)]
        value = self.run_command('writing time', 'cd'*12)
        self.assertTrue(value['error']); self.assertEqual(len(value['steps']), 1)
        self.assertEqual(self.run_command('writing time', 'cd'*12), value)
        self.assertEqual(self.runner.call_count, 2)

    def test_interrupted_receipt_is_never_replayed(self):
        self.assistant.state['receipts'][KEY] = {'input': json.dumps(['Open Safari', None]), 'result': {'matched': True, 'error': True, 'answer': 'Started but unconfirmed'}}
        self.assistant.save()
        value = actions.Assistant(self.path, self.runner).execute('Open Safari', KEY)
        self.assertTrue(value['error']); self.runner.assert_not_called()

    def test_missing_or_invalid_key_is_refused_before_actions(self):
        for key in (None, '', 'bad', 123):
            with self.assertRaises(actions.CommandError):
                self.run_command('Open Safari', key)
        self.runner.assert_not_called()

    def test_window_requires_real_helper_and_valid_target(self):
        with patch.object(actions, 'DESKTOP_BINARY', Path(self.scratch.name) / 'missing'):
            value = self.run_command('Move window left')
        self.assertTrue(value['error']); self.runner.assert_not_called()

    def test_same_origin_and_replay_guard_apply_to_http(self):
        with patch.object(server, 'ASSISTANT', self.assistant):
            self.assertEqual(request('/assistant/command', 'POST', {'question': 'Open Safari', 'request_key': KEY})[0], 403)
            status, _, raw = request('/assistant/command', 'POST', {'question': 'Open Safari', 'request_key': KEY}, ORIGIN)
            self.assertEqual(status, 200); self.assertTrue(json.loads(raw)['matched'])
            self.assertEqual(request('/assistant/command', 'POST', {'question': 'Open Safari', 'request_key': KEY}, ORIGIN)[0], 200)
            self.runner.assert_called_once()

    def test_background_handoff_uses_existing_workflow_and_admission_key(self):
        with patch.object(server.WORKFLOWS, 'start', return_value={'id': 'cd'*12}) as start:
            status, _, raw = request('/assistant/command', 'POST', {'question': 'Background task: compare the pricing notes', 'request_key': KEY}, ORIGIN)
            self.assertEqual(status, 200); self.assertEqual(json.loads(raw)['workflow_run'], 'cd'*12)
            start.assert_called_once_with('compare the pricing notes', 'research', request_key=KEY)
            self.assertEqual(request('/assistant/command', 'POST', {'question': 'Background task: hello'}, ORIGIN)[0], 400)

    def test_verbatim_dictation_never_calls_a_model(self):
        with patch.object(server, 'ask_brain') as brain:
            status, _, raw = request('/assistant/dictation', 'POST', {'text': 'send that email now', 'cleanup': False}, ORIGIN)
            self.assertEqual(status, 200); self.assertEqual(json.loads(raw)['text'], 'send that email now'); brain.assert_not_called()

    def test_cleanup_failure_cannot_replace_transcript_with_an_error(self):
        with patch.object(server, 'ask_brain', return_value={'error': True, 'answer': 'backend failed'}):
            status, _, raw = request('/assistant/dictation', 'POST', {'text': 'my original words', 'cleanup': True}, ORIGIN)
            self.assertEqual(status, 400); self.assertNotIn('text', json.loads(raw))

    def test_focus_not_advertised_or_callable(self):
        self.assertNotIn('focus', json.loads(request('/system')[2])['capabilities'])
        self.assertFalse(any(item['name'].startswith('focus_') for item in server.ultra_tools.SPECS))


class SensorTests(unittest.TestCase):
    def test_only_opt_in_camera_booleans_are_stored_and_expire(self):
        now = [10.0]; sensor = sensor_state.Sensors(lambda: now[0])
        self.assertFalse(sensor.state()['eyes_active'])
        signals = dict(eyes_active=True, present=True, head_down=False, slouched=False)
        self.assertTrue(sensor.update(signals)['present'])
        sensor.relief(); now[0] += sensor_state.SIGNAL_LEASE_S
        self.assertFalse(sensor.state()['eyes_active']); self.assertGreater(sensor.state()['snooze_s'], 0)
        self.assertEqual(set(vars(sensor)), {'clock', 'lock', 'signals', 'updated', 'quiet_until'})
        with self.assertRaises(ValueError): sensor.update({'eyes_active': 'true'})


if __name__ == '__main__':
    unittest.main()
