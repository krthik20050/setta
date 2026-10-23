import threading
import unittest
from unittest.mock import Mock
from src.webcam import WebcamCapture


class ShutdownTests(unittest.TestCase):
    def test_stop_request_does_not_close_active_detector(self):
        camera = WebcamCapture()
        detector = Mock()
        camera._face_detector = detector
        camera.release()
        camera.release()
        self.assertTrue(camera._stop.is_set())
        detector.close.assert_not_called()

    def test_cleanup_runs_once_on_owner_even_after_failure(self):
        camera = WebcamCapture()
        closed = []
        detector = Mock()
        detector.close.side_effect = lambda: closed.append(threading.get_ident())
        camera._face_detector = detector
        # Detectors belong to the analysis worker after preview/analysis were split.
        camera._analyze_frames = Mock(side_effect=RuntimeError('inference failed'))
        owner = threading.Thread(target=camera._analysis_owned)
        owner.start()
        owner.join()
        camera.release()
        self.assertEqual(closed, [owner.ident])
        self.assertIsNone(camera._face_detector)
