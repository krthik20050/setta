import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from src.character_profile import CharacterProfile
from src.paths import PROJECT_ROOT
from src.webcam import WebcamCapture


class ControlTests(unittest.TestCase):
    def test_camera_starts_only_on_request_stops_and_can_restart_without_duplicate_owner(self):
        camera = WebcamCapture()
        self.assertIsNone(camera._thread)
        self.assertEqual(camera.status, 'Camera off')
        entered = threading.Event()
        runs = []
        def capture():
            runs.append(threading.get_ident())
            entered.set()
            camera._stop.wait(2)
        camera._capture = capture
        self.assertTrue(camera.start())
        self.assertTrue(entered.wait(1))
        owner = camera._thread
        self.assertTrue(camera.start())
        self.assertIs(camera._thread, owner)
        camera.latest_face = (0, Mock())
        camera.latest_frame = (0, Mock())
        camera.release()
        owner.join(2)
        self.assertFalse(owner.is_alive())
        self.assertIsNone(camera.latest_face)
        self.assertIsNone(camera.latest_frame)
        self.assertIsNone(camera.activity.last_seen)
        entered.clear()
        self.assertTrue(camera.start())
        self.assertTrue(entered.wait(1))
        self.assertIsNot(camera._thread, owner)
        camera.release()
        camera._thread.join(2)
        self.assertEqual(len(runs), 2)

    def test_profile_edits_preserve_other_configuration_and_refresh_existing_reader(self):
        parent = PROJECT_ROOT/'runtime'/'profile-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            path = Path(directory)/'amma.json'
            initial = {'name': 'Amma', 'role': 'Mother', 'custom_instructions': '',
                       'context': {'camera_on_request': True}, 'pronunciations': {'en-IN': {'Setta': 'Setta'}},
                       'greetings': {'speak': False}, 'future_field': {'keep': 1}}
            path.write_text(json.dumps(initial), encoding='utf-8')
            reader = CharacterProfile.load(path)
            CharacterProfile.save_personality({'name': 'Mama', 'role': 'A caring mother',
                'custom_instructions': 'Use short, playful replies.'}, path)
            stored = json.loads(path.read_text())
            for key in ('context', 'pronunciations', 'greetings', 'future_field'):
                self.assertEqual(stored[key], initial[key])
            instructions = reader.instructions('en-IN')
            self.assertIn('Mama', instructions)
            self.assertIn('short, playful', instructions)
            with self.assertRaises(ValueError):
                CharacterProfile.save_personality({'name': ''}, path)
            self.assertEqual(json.loads(path.read_text()), stored)
