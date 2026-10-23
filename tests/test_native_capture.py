from array import array
import threading
import unittest
from unittest.mock import Mock, patch
from src.native_capture import MonitoredStream
from src.sarvam_voice import SarvamVoiceAgent


class NativeCaptureTests(unittest.TestCase):
    def test_background_reply_work_does_not_reject_later_user_speech(self):
        source = Mock()
        source.read.return_value = array('h', [1800]*1024).tobytes()
        playing = False
        stream = MonitoredStream(source, lambda: 500, Mock(), playback_active=lambda: playing)
        # Listening can begin during reply generation; that is not speaker audio.
        for _ in range(4): stream.read(1024)
        self.assertFalse(stream.speaker_audio_detected)
        playing = True
        stream.read(1024)
        self.assertTrue(stream.speaker_audio_detected)
        stream.reset()
        playing = False
        for _ in range(4): stream.read(1024)
        self.assertFalse(stream.speaker_audio_detected)

    def test_sustained_speech_triggers_once_per_utterance(self):
        source = Mock()
        quiet = array('h', [0]*1024).tobytes()
        speech = array('h', [1600]*1024).tobytes()
        source.read.side_effect = [quiet, speech, speech, quiet, speech, speech, speech, speech]
        onset = Mock()
        stream = MonitoredStream(source, lambda: 500, onset)
        for _ in range(8): stream.read(1024)
        onset.assert_called_once()
        stream.reset()
        source.read.side_effect = None
        source.read.return_value = speech
        for _ in range(3): stream.read(1024)
        self.assertEqual(onset.call_count, 2)

    def test_interrupt_stops_reply_without_stopping_microphone_session(self):
        agent = SarvamVoiceAgent('test')
        agent.active = True
        with patch('src.sarvam_voice.winsound.PlaySound') as playback:
            agent.interrupt()
        self.assertTrue(agent._turn_cancel.is_set())
        self.assertFalse(agent._stop.is_set())
        self.assertTrue(agent.active)
        playback.assert_called_with(None, 0)

    def test_old_reply_remains_cancelled_even_if_event_is_cleared(self):
        agent = SarvamVoiceAgent('test')
        agent._reply_epoch = agent._epoch
        with patch('src.sarvam_voice.winsound.PlaySound'):
            agent.interrupt()
        agent._turn_cancel.clear()  # Simulate a concurrent next-turn setup.
        self.assertTrue(agent._cancelled())

    def test_cancelled_reply_does_not_start_tts_or_playback(self):
        from src.sarvam_conversation import RecognizedTurn
        agent = SarvamVoiceAgent('test')
        conversation = Mock()
        def reply(turn):
            agent.interrupt()
            return 'A stale answer'
        conversation.reply.side_effect = reply
        with patch('src.sarvam_voice.winsound.PlaySound'):
            agent._process_turn(conversation, RecognizedTurn('Hello', 'en-IN', None, False))
        conversation.synthesize.assert_not_called()
