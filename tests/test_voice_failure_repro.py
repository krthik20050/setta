import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.sarvam_voice import SarvamVoiceAgent


class VoiceFailureRegressionTests(unittest.TestCase):
    def test_explicit_voice_start_enables_spoken_replies(self):
        agent=SarvamVoiceAgent('test')
        with patch('src.sarvam_voice.threading.Thread'):
            agent.start()
        self.assertFalse(agent.muted)

    def test_malformed_tts_wave_is_reported_instead_of_silent_thread_death(self):
        import wave
        agent=SarvamVoiceAgent('test')
        agent.on_text_final=Mock()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.tools') as folder:
            with patch('src.sarvam_voice.RUNTIME_DIR',Path(folder)), patch('src.sarvam_voice.LiveConversation',side_effect=wave.Error('bad WAV')):
                agent._run()
                self.assertTrue((Path(folder)/'voice-error.json').exists())
        agent.on_text_final.assert_called_once()
        self.assertIn('Voice mode stopped',agent.on_text_final.call_args.args[0])
        self.assertFalse(agent.active)
