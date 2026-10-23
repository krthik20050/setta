import tempfile
import unittest
from pathlib import Path
import numpy as np
from src.face_id import FaceID
from src.paths import PROJECT_ROOT

class FaceCandidateTests(unittest.TestCase):
    def setUp(self):
        parent = PROJECT_ROOT / 'runtime' / 'candidate-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.faces = FaceID(Path(self.temp.name), '')
        self.embedding = np.arange(1, 17, dtype=float)
        self.faces.register_face('Papa', self.embedding)
        self.photo = np.random.default_rng(11).integers(45, 210, (100, 100, 3), dtype=np.uint8)

    def collect(self):
        return [self.faces.consider_candidate('Papa', self.embedding, self.photo, now=t) for t in (1, 3, 5)]

    def test_disabled_and_unknown_do_not_collect(self):
        self.assertEqual(self.collect(), [False, False, False])
        self.faces.capture_candidates = True
        self.assertFalse(self.faces.consider_candidate('Unknown', self.embedding, self.photo, now=7))
        self.assertIsNone(self.faces.list_faces()[0]['candidate'])

    def test_repeated_match_requires_review_before_reference_changes(self):
        self.faces.capture_candidates = True
        self.assertEqual(self.collect(), [False, False, True])
        row = self.faces.list_faces()[0]
        self.assertEqual(row['samples'], 1)
        self.assertIsNotNone(row['candidate'])
        self.assertIsNone(row['thumbnail'])
        self.assertFalse(self.faces.consider_candidate('Papa', self.embedding, self.photo, now=700))
        self.faces.review_candidate('Papa', True)
        row = self.faces.list_faces()[0]
        self.assertEqual(row['samples'], 2)
        self.assertIsNotNone(row['thumbnail'])
        self.assertIsNone(row['candidate'])

    def test_dismiss_and_remove_delete_pending_photos(self):
        self.faces.capture_candidates = True
        self.collect()
        self.faces.review_candidate('Papa', False)
        self.assertEqual(self.faces.list_faces()[0]['samples'], 1)
        self.assertIsNone(self.faces.list_faces()[0]['candidate'])
        self.faces.remove_face('Papa')
        self.assertEqual(self.faces.list_faces(), [])

    def test_blurry_and_ambiguous_faces_are_rejected(self):
        self.faces.capture_candidates = True
        self.assertFalse(self.faces.consider_candidate('Papa', self.embedding, np.full((100,100,3), 100, dtype=np.uint8), now=1))
        self.faces.register_face('Uncle', self.embedding + .001)
        self.assertEqual(self.collect(), [False, False, False])
