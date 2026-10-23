import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import wave

from src.greeting_speech import canonical_greeting, MANGGLISH_GREETING, NATIVE_GREETING, cached_greeting_audio
from src.sarvam_conversation import RecognizedTurn
from src.sarvam_voice import SarvamVoiceAgent


class GreetingSpeechTests(unittest.TestCase):
    def test_known_greeting_skips_model_rewriting(self):
        agent = SarvamVoiceAgent('test')
        conversation = MagicMock()
        with patch('src.sarvam_voice.LiveConversation', return_value=conversation), \
             patch('src.sarvam_voice.SarvamConversation.reply') as rewrite, \
             patch('src.sarvam_voice.cached_greeting_audio', return_value=b'cached-wave') as cache, \
             patch.object(agent, '_play'):
            agent._greet(MANGGLISH_GREETING, 'ml-IN')
        rewrite.assert_not_called()
        self.assertEqual(cache.call_args.args[1], NATIVE_GREETING)
        self.assertFalse(cache.call_args.args[2].mixed)
        self.assertIsNone(canonical_greeting('A new custom greeting', 'ml-IN'))
        self.assertIsNone(canonical_greeting(MANGGLISH_GREETING, 'en-IN'))

    def test_cache_reuses_audio_and_invalidates_on_delivery_change(self):
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
            wav.writeframes(b'\0\0'*2400)
        conversation = MagicMock()
        conversation.voice_for.return_value = ('approved-voice-8', 8)
        conversation.profile.data = {'speech_delivery': {'pace':1.18}, 'pronunciations':{}}
        conversation.synthesize.return_value = stream.getvalue()
        turn = RecognizedTurn(NATIVE_GREETING, 'ml-IN', None, False)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            for _ in range(2):
                self.assertEqual(cached_greeting_audio(conversation, NATIVE_GREETING, turn,
                                                      NATIVE_GREETING, Path(folder)), stream.getvalue())
            self.assertEqual(conversation.synthesize.call_count, 1)
            conversation.profile.data['speech_delivery']['pace'] = 1.2
            cached_greeting_audio(conversation, NATIVE_GREETING, turn, NATIVE_GREETING, Path(folder))
            self.assertEqual(conversation.synthesize.call_count, 2)
