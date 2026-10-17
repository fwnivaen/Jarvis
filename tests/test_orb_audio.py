"""Private local speech resources: bounded input, opaque access, and cleanup."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import voice_bridge


class OrbAudioTests(unittest.TestCase):
    def tearDown(self):
        for token in list(voice_bridge.AUDIO):
            voice_bridge.release_audio(token)

    @staticmethod
    def rendered(arguments, **kwargs):
        Path(arguments[arguments.index('-o') + 1]).write_bytes(b'RIFF-test-wave')
        return subprocess.CompletedProcess(arguments, 0)

    def test_input_boundaries_do_not_launch_speech(self):
        with patch.object(voice_bridge.subprocess, 'run') as run:
            for text in ('', '   ', None, ['text'], 'x' * (voice_bridge.AUDIO_TEXT_CHARS + 1)):
                self.assertEqual(voice_bridge.render_audio(text)['status'], 'error')
            run.assert_not_called()

    def test_temporary_token_resource_cannot_name_files_and_releases(self):
        with patch.object(voice_bridge.subprocess, 'run', side_effect=self.rendered) as run:
            rendered = voice_bridge.render_audio('A local answer, sir.')
        self.assertEqual(rendered['status'], 'ready')
        token = rendered['token']
        folder = voice_bridge.AUDIO[token]['path'].parent
        self.assertEqual(voice_bridge.read_audio(token), b'RIFF-test-wave')
        self.assertIsNone(voice_bridge.read_audio('../../config.json'))
        self.assertEqual(run.call_args.kwargs['input'], 'A local answer, sir.')
        self.assertEqual(run.call_args.kwargs['timeout'], voice_bridge.AUDIO_RENDER_TIMEOUT_S)
        self.assertIn('Daniel', run.call_args.args[0])
        voice_bridge.release_audio(token)
        self.assertIsNone(voice_bridge.read_audio(token))
        self.assertFalse(folder.exists())

    def test_expired_tokens_and_render_timeouts_clean_up(self):
        with patch.object(voice_bridge.subprocess, 'run', side_effect=self.rendered), patch.object(voice_bridge.time, 'monotonic', return_value=100):
            rendered = voice_bridge.render_audio('A local answer.')
        token = rendered['token']
        folder = voice_bridge.AUDIO[token]['path'].parent
        with patch.object(voice_bridge.time, 'monotonic', return_value=100 + voice_bridge.AUDIO_LEASE_S + 1):
            self.assertIsNone(voice_bridge.read_audio(token))
        self.assertFalse(folder.exists())
        with patch.object(voice_bridge.subprocess, 'run', side_effect=subprocess.TimeoutExpired('say', voice_bridge.AUDIO_RENDER_TIMEOUT_S)):
            self.assertEqual(voice_bridge.render_audio('A local answer.')['status'], 'error')
        self.assertEqual(voice_bridge.AUDIO, {})


if __name__ == '__main__':
    unittest.main()
