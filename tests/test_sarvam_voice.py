import io
import threading
import unittest
from unittest.mock import Mock, patch
import wave
import tempfile
from pathlib import Path

from src.sarvam_voice import SarvamVoiceAgent
from src.sarvam_conversation import RecognizedTurn, ReplyLanguageError


class VoiceLifecycleTests(unittest.TestCase):
    def test_transcript_precedes_reply_and_reply_caption_precedes_audio(self):
        agent = SarvamVoiceAgent('test')
        events = []
        agent.on_transcript = lambda text: events.append(('you', text))
        agent.on_text_partial = lambda text: events.append(('amma', text))
        conversation = Mock()
        conversation.reply.side_effect = lambda turn: events.append(('reply', turn.text)) or 'Hello there.'
        conversation.synthesize.side_effect = lambda *args: events.append(('tts', args[0])) or b'wav'
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            with patch('src.sarvam_voice.RUNTIME_DIR', Path(folder)), \
                 patch.object(agent, '_play', side_effect=lambda audio: events.append(('play', audio))):
                agent._process_turn(conversation, RecognizedTurn('Hello', 'en-IN', None, False))
        self.assertEqual([event[0] for event in events], ['you', 'reply', 'tts', 'amma', 'play'])

    def test_failed_language_turn_keeps_microphone_session_for_next_turn(self):
        from unittest.mock import MagicMock
        agent = SarvamVoiceAgent('test')
        agent.realtime_input = False  # Exercise the explicitly retained REST fallback.
        agent.active = True
        conversation = Mock()
        conversation.memory.recent.return_value = []
        conversation.recognize.return_value = RecognizedTurn('English please', 'en-IN', None, False)
        conversation.reply.side_effect = [ReplyLanguageError('Please repeat; still listening.'), 'All right.']
        def final(text):
            if text == 'All right.':
                agent._stop.set()
        agent.on_text_final = final
        recognizer = MagicMock()
        recognizer.listen.return_value.frame_data = b'\0\0' * 1600
        recognizer.listen.return_value.sample_rate = 16000
        recognizer.listen.return_value.sample_width = 2
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder, \
             patch('src.sarvam_voice.RUNTIME_DIR', Path(folder)), \
             patch('src.sarvam_voice.LiveConversation', return_value=conversation), \
             patch('src.sarvam_voice.sr.Recognizer', return_value=recognizer), \
             patch('src.sarvam_voice.sr.Microphone', return_value=MagicMock()), \
             patch.object(agent, '_play'):
            agent._run()
        self.assertEqual(conversation.reply.call_count, 2)
        conversation.close.assert_called_once()
    def test_start_does_not_spawn_over_an_existing_worker(self):
        agent=SarvamVoiceAgent('test')
        agent._thread=Mock()
        agent._thread.is_alive.return_value=True
        agent.on_text_final=Mock()
        with patch('src.sarvam_voice.threading.Thread') as spawn:
            agent.start()
        spawn.assert_not_called()
        agent.on_text_final.assert_called_once()

    def test_stopped_reply_never_starts_playback(self):
        agent=SarvamVoiceAgent('test')
        agent._stop.set()
        with patch('src.sarvam_voice.winsound.PlaySound') as playback:
            agent._play(b'not even decoded after stop')
        playback.assert_not_called()

    def test_stop_interrupts_playback_and_cleans_up(self):
        stream=io.BytesIO()
        with wave.open(stream,'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000)
            audio.writeframes(b'\0\0'*24000*5)
        agent=SarvamVoiceAgent('test')
        started=threading.Event()
        def playback(path, flags):
            if path is not None: started.set()
        with patch('src.sarvam_voice.winsound.PlaySound',side_effect=playback) as player:
            worker=threading.Thread(target=agent._play,args=(stream.getvalue(),))
            worker.start()
            self.assertTrue(started.wait(2))
            agent.stop();worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertTrue(agent._stop.is_set())
            self.assertGreaterEqual(sum(call.args[0] is None for call in player.call_args_list),1)


if __name__=='__main__': unittest.main()
