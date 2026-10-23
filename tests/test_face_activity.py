import unittest
from src.face_activity import FaceActivity


class ActivityTests(unittest.TestCase):
    def test_speech_openings_do_not_trigger(self):
        tracker = FaceActivity()
        for i in range(20):
            self.assertFalse(tracker.update(i * .4, jaw=.8))
            self.assertFalse(tracker.update(i * .4 + .2, jaw=.1))

    def test_completed_yawn_and_cooldown(self):
        tracker = FaceActivity()
        self.assertFalse(tracker.update(0, jaw=.8))
        tracker.update(.5, jaw=.8)
        tracker.update(1, jaw=.8)
        tracker.update(1.5, jaw=.8)
        tracker.update(2, jaw=.8)
        self.assertTrue(tracker.update(2.2, jaw=.1))
        tracker.update(3, jaw=.8)
        tracker.update(3.5, jaw=.8)
        tracker.update(4, jaw=.8)
        tracker.update(4.5, jaw=.8)
        tracker.update(5, jaw=.8)
        self.assertFalse(tracker.update(5.2, jaw=.1))

    def test_tracking_loss_cancels_yawn(self):
        tracker = FaceActivity()
        tracker.update(0, jaw=.8)
        tracker.update(.5, jaw=.8)
        tracker.update(1, present=False)
        self.assertFalse(tracker.update(2, jaw=.1))

    def test_frame_gap_cancels_yawn(self):
        tracker = FaceActivity()
        tracker.update(0, jaw=.8)
        self.assertFalse(tracker.update(3, jaw=.1))

    def test_eyes_closed_is_observation(self):
        tracker = FaceActivity()
        for i in range(7):
            tracker.update(i * .5, eyes=.9)
        self.assertIn('Eyes closed', tracker.summary)
