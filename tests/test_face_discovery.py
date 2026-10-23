import tempfile
import unittest
from pathlib import Path
import numpy as np
from src.face_id import FaceID
from src.paths import PROJECT_ROOT

class FaceDiscoveryTests(unittest.TestCase):
    def setUp(self):
        parent=PROJECT_ROOT/'runtime'/'discovery-tests'; parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.faces=FaceID(self.root/'known_faces','')
        self.embedding=np.random.default_rng(4).normal(size=32)
        self.photo=np.random.default_rng(8).integers(45,210,(100,100,3),dtype=np.uint8)

    def test_capture_label_restart_and_recognize_actual_sample(self):
        key=self.faces.inbox.add(self.embedding,self.photo,now=1)
        self.assertTrue(key)
        self.assertEqual(len(self.faces.inbox.rows()),1)
        self.assertEqual(self.faces.match_face(self.embedding),'Unknown')
        self.faces.inbox.label(key,'Papa',self.faces.register_face)
        restarted=FaceID(self.root/'known_faces','')
        self.assertEqual(restarted.inbox.rows(),[])
        self.assertEqual(restarted.match_face(self.embedding),'Papa')
        self.assertTrue(restarted.list_faces()[0]['thumbnail'])

    def test_duplicate_capture_grouping_and_existing_person_sample(self):
        key=self.faces.inbox.add(self.embedding,self.photo,now=1)
        self.assertEqual(self.faces.inbox.add(self.embedding+.001,self.photo,now=8),key)
        self.assertEqual(len(self.faces.inbox.rows()),1)
        self.faces.register_face('Papa',self.embedding)
        self.faces.inbox.label(key,'Papa',self.faces.register_face)
        self.assertEqual(self.faces.list_faces()[0]['samples'],2)

    def test_failed_label_keeps_capture_and_discard_removes_it(self):
        key=self.faces.inbox.add(self.embedding,self.photo,now=1)
        with self.assertRaises(ValueError):
            self.faces.inbox.label(key,'../outside',self.faces.register_face)
        self.assertEqual(len(self.faces.inbox.rows()),1)
        self.faces.inbox.discard(key)
        self.assertEqual(self.faces.inbox.rows(),[])

    def test_blurry_face_is_not_collected_and_queue_is_bounded(self):
        self.assertIsNone(self.faces.inbox.add(self.embedding,np.full((100,100,3),100,dtype=np.uint8),now=1))
        for index in range(15):
            vector=np.zeros(32); vector[index]=1
            self.faces.inbox.add(vector,self.photo,now=index*4+1)
        self.assertEqual(len(self.faces.inbox.rows()),12)
    def test_first_unknown_face_can_be_discovered_with_no_enrolled_people(self):
        import sys, types, time
        from unittest.mock import Mock, patch
        fake=types.ModuleType('deepface.DeepFace')
        fake.represent=lambda **kwargs: [{'embedding':self.embedding}]
        self.faces.discover_faces=True
        callback=Mock()
        with patch.dict(sys.modules,{'deepface.DeepFace':fake}):
            self.faces.identify_async(self.photo,callback)
            deadline=time.monotonic()+2
            while self.faces.busy and time.monotonic()<deadline: time.sleep(.01)
        callback.assert_called_once_with('Unknown')
        self.assertEqual(len(self.faces.inbox.rows()),1)
        self.assertEqual(self.faces.known_face_embeddings,{})
