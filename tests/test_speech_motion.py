import io
import unittest
import wave
import numpy as np
from src.speech_motion import SpeechMotion
from src.pronunciation import spoken_text


class SpeechMotionTests(unittest.TestCase):
    def test_pause_closes_actual_pose_mouth_and_speech_moves_mouth_and_hands(self):
        motion = SpeechMotion((0, .3, .6, .95)*50, .05, 10)
        self.assertEqual(motion.frame_at(0), 0)
        self.assertEqual(motion.frame_at(10), 0)
        indices = {motion.frame_at(i*.05) for i in range(200)}
        self.assertTrue(any(1 <= i <= 3 for i in indices))
        self.assertTrue(any(5 <= i <= 7 for i in indices))
        self.assertTrue(all(0 <= i < 8 for i in indices))

    def test_wav_envelope_is_based_on_audio_not_a_timer_loop(self):
        samples = np.concatenate([np.zeros(2400), np.sin(np.arange(4800)*.2)*12000, np.zeros(2400)]).astype('<i2')
        data = io.BytesIO()
        with wave.open(data, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
            wav.writeframes(samples.tobytes())
        motion = SpeechMotion.from_wav(data.getvalue())
        self.assertAlmostEqual(motion.duration, .4)
        self.assertEqual(motion.frame_at(.01), 0)
        self.assertGreater(motion.frame_at(.15), 0)
        self.assertEqual(motion.frame_at(.35), 0)

    def test_pronunciation_replaces_whole_words_only_in_the_requested_language(self):
        rules = {'ml-IN': {'API':'A P I', 'Karthik':'Kaarthik'}}
        original = 'API and APIS for Karthik.'
        self.assertEqual(spoken_text(original, 'ml-IN', rules), 'A P I and APIS for Kaarthik.')
        self.assertEqual(spoken_text(original, 'en-IN', rules), original)
        self.assertEqual(original, 'API and APIS for Karthik.')
