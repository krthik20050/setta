import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.desktop_activity import DesktopActivity, desktop_question


class DesktopActivityTests(unittest.TestCase):
    def test_history_survives_restart_and_tracks_observed_titles_only(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            reader = Mock(side_effect=[{'app':'Codex.exe','title':'PROJECT SETTA - Codex'},
                                      {'app':'Codex.exe','title':'PROJECT SETTA - Codex'},
                                      None, {'app':'Code.exe','title':'README.md'}])
            tracker = DesktopActivity(Path(folder)/'activity.sqlite', {'foreground_app':True}, reader)
            for _ in range(4): tracker.poll()
            evidence = tracker.observations()
            rows = json.loads(evidence[-1].value)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['app'], 'Code.exe')
            self.assertEqual(rows[1]['title'], 'PROJECT SETTA - Codex')
            restarted = DesktopActivity(tracker.path, {}, lambda:None)
            self.assertEqual(len(json.loads(restarted.observations()[-1].value)), 2)

    def test_disabled_tracker_does_not_start_background_reader(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            reader = Mock()
            tracker = DesktopActivity(Path(folder)/'activity.sqlite', {'foreground_app':False}, reader)
            tracker.start()
            self.assertIsNone(tracker._thread)
            reader.assert_not_called()
        self.assertTrue(desktop_question('What was I working on?'))
        self.assertTrue(desktop_question('Which app is active?'))
        self.assertFalse(desktop_question('How are you?'))
