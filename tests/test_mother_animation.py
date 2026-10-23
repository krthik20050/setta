from pathlib import Path
import unittest
from src.mother_animation import animation_frames, load_poses, approved_fullbody


SHEET = Path(__file__).resolve().parents[1] / 'assets/mother/artwork/mother-expressions-v2.png'


class MotherAnimationTests(unittest.TestCase):
    def test_all_poses_fit_and_share_ground_line(self):
        poses = load_poses(SHEET)
        self.assertEqual(len(poses), 16)
        for pose in poses:
            self.assertEqual(pose.size, (192, 208))
            bounds = pose.getchannel('A').getbbox()
            self.assertIsNotNone(bounds)
            self.assertEqual(bounds[3], 202)
            self.assertGreater(bounds[0], 0)
            self.assertLess(bounds[2], 192)

    def test_user_actions_have_valid_animation_sequences(self):
        frames = animation_frames(SHEET)
        for state in ('idle', 'walk', 'wave', 'love', 'scold', 'angry', 'proud',
                      'voice_listening', 'voice_thinking', 'review'):
            self.assertTrue(frames[state])
        self.assertEqual(len(frames['walk']), 8)
        self.assertNotEqual(frames['scold'][0].tobytes(), frames['scold'][2].tobytes())

    def test_new_emotions_and_laughter_have_distinct_frames(self):
        frames = animation_frames(SHEET, (144, 160))
        for state in ('laugh', 'sad', 'concern', 'smile'):
            self.assertTrue(frames[state])
        self.assertGreaterEqual(len({f.tobytes() for f in frames['laugh']}), 4)
        for state in ('laugh', 'sad', 'concern', 'love', 'proud', 'walk'):
            for frame in frames[state]:
                self.assertEqual(frame.size, (144, 160))
                self.assertLessEqual(frame.getchannel('A').getbbox()[3], 154)


class ProportionTests(unittest.TestCase):
    def test_conversation_rest_keeps_the_same_portrait_between_spoken_chunks(self):
        frames = animation_frames(SHEET, (240,336))
        self.assertEqual(frames['conversation_rest'][0].tobytes(), frames['talk'][0].tobytes())

    def test_talking_uses_eight_baked_mouth_and_gesture_poses(self):
        frames = animation_frames(SHEET, (240,336))['talk']
        self.assertEqual(len(frames), 8)
        self.assertEqual(len({f.tobytes() for f in frames}), 8)
        for frame in frames:
            self.assertEqual(frame.getchannel('A').getbbox()[3], 330)
            self.assertTrue(set(frame.getchannel('A').tobytes()) <= {0,255})

    def test_approved_figure_has_full_height_and_no_background_fringe(self):
        import numpy as np
        image = approved_fullbody(SHEET.with_name('mother-likeness-v6.png'), (240, 336))
        alpha = np.array(image)[:, :, 3]
        self.assertEqual(set(np.unique(alpha)), {0, 255})
        self.assertEqual(image.getchannel('A').getbbox()[3], 330)
        self.assertGreater(image.getchannel('A').getbbox()[3]-image.getchannel('A').getbbox()[1], 300)

    def test_standing_and_walking_have_matching_full_body_height(self):
        frames = animation_frames(SHEET, (144, 160))
        heights = []
        for state in ('idle', 'walk', 'wave', 'love', 'proud', 'scold', 'angry'):
            box = frames[state][0].getchannel('A').getbbox()
            heights.append(box[3] - box[1])
            self.assertEqual(box[3], 154)
        self.assertLessEqual(max(heights) - min(heights), 2)
