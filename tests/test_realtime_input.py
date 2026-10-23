import unittest
from src.realtime_input import TranscriptTurn


class TranscriptTurnTests(unittest.TestCase):
    def test_partials_are_revised_and_never_committed(self):
        state = TranscriptTurn()
        state.accept({'event':'transcript.partial','text':'I am going'}, 0)
        state.accept({'event':'transcript.partial','text':'I am going to wash'}, .3)
        self.assertEqual(state.preview, 'I am going to wash')
        self.assertFalse(state.ready(100))

    def test_resume_before_commit_joins_segments(self):
        state = TranscriptTurn()
        state.accept({'event':'transcript.final','text':'I am going to wash','language':'en-IN'}, 0)
        self.assertFalse(state.ready(.7))
        state.accept({'event':'vad.speech_start'}, .8)
        self.assertFalse(state.ready(10))
        state.accept({'event':'transcript.final','text':'the laundry','language':'en-IN'}, 11)
        self.assertTrue(state.ready(12))
        self.assertEqual(state.preview, 'I am going to wash the laundry')

    def test_empty_final_does_not_create_phantom_turn(self):
        state = TranscriptTurn()
        state.accept({'event':'transcript.final','text':''}, 0)
        self.assertFalse(state.ready(10))

    def test_long_turn_has_no_27_second_commit(self):
        state = TranscriptTurn()
        for second in range(60):
            state.accept({'event':'transcript.partial','text':f'Continuing thought {second}'}, second)
            self.assertFalse(state.ready(second))
        state.accept({'event':'transcript.final','text':'A complete long thought','language':'en-IN'}, 61)
        self.assertTrue(state.ready(62))

    def test_streaming_final_uses_same_reply_path_without_rest_transcription(self):
        import queue
        import speech_recognition as sr
        from unittest.mock import Mock, patch
        from src.sarvam_voice import SarvamVoiceAgent
        from src.sarvam_conversation import RecognizedTurn
        agent = SarvamVoiceAgent('test')
        agent.on_transcript_partial = Mock()
        agent.on_transcript = Mock()
        conversation = Mock()
        pending = queue.Queue(maxsize=1)
        turn = RecognizedTurn('I am going to wash the laundry', 'en-IN', None, False)
        def capture(key, stop, playing, partial, speaking, status):
            speaking(True)
            partial('I am going to wash')
            speaking(False)
            yield sr.AudioData(b'\0\0'*16000,16000,2), turn
        with patch('src.sarvam_voice.capture_turns', capture), patch('src.sarvam_voice.winsound.PlaySound'):
            agent._run_realtime(conversation, pending)
        agent.on_transcript_partial.assert_called_once_with('I am going to wash')
        self.assertIs(pending.get_nowait()[3], turn)
        conversation.recognize.assert_not_called()
