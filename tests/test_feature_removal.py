"""Keep the original Jarvis routes while retiring the requested additions."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import sensor_state
import server
import voice_bridge
from test_offline import request

ROOT = Path(__file__).resolve().parents[1]


class FeatureRemovalTests(unittest.TestCase):
    def test_removed_routes_cannot_execute(self):
        paths = ('/assistant', '/assistant/command', '/assistant/dictation',
                 '/assistant/shortcut', '/assistant/desktop', '/voice/finish',
                 '/voice/setup', '/voice/status', '/focus', '/attention')
        with patch.object(voice_bridge, 'handle') as voice:
            for path in paths:
                self.assertEqual(request(path, 'POST', {}, {'Origin': 'http://127.0.0.1:4700'})[0], 404, path)
            for path in ('/assistant', '/assistant.js', '/assistant.css', '/focus', '/focus/diag'):
                self.assertEqual(request(path)[0], 404, path)
        voice.assert_not_called()

    def test_original_services_and_tools_remain(self):
        capabilities = json.loads(request('/system')[2])['capabilities']
        for key in ('notes', 'eyes', 'screen', 'models'):
            self.assertTrue(capabilities[key])
        for key in ('focus', 'shortcuts', 'dictation'):
            self.assertNotIn(key, capabilities)
        names = {item['name'] for item in server.ultra_tools.SPECS}
        self.assertIn('notes_search', names)
        self.assertIn('screen_watch_status', names)
        self.assertFalse(any(name.startswith('focus_') for name in names))

    def test_original_dashboard_and_launchers_have_no_removed_hooks(self):
        for name in ('viewer/index.html', 'viewer/ui.js', 'start.sh', 'start-workflows.sh'):
            text = (ROOT / name).read_text()
            for removed in ('JarvisAssistant', 'JarvisFocus', 'rail-assistant', 'rail-focus', 'native/prepare.sh'):
                self.assertNotIn(removed, text)
        self.assertIn('class MacRecognition', (ROOT / 'viewer/index.html').read_text())

    def test_opt_in_camera_state_survives_without_focus(self):
        now = [10.0]
        sensor = sensor_state.Sensors(lambda: now[0])
        self.assertFalse(sensor.state()['eyes_active'])
        sensor.update(dict(eyes_active=True, present=True, head_down=False, slouched=False))
        self.assertTrue(sensor.state()['present'])
        sensor.relief()
        now[0] += sensor_state.SIGNAL_LEASE_S
        self.assertFalse(sensor.state()['eyes_active'])
        self.assertGreater(sensor.state()['snooze_s'], 0)


if __name__ == '__main__':
    unittest.main()
