import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import httpx
import numpy as np
from src.paths import PROJECT_ROOT
from src.webcam import WebcamCapture
from src.local_reminders import LocalReminders
from src.reminder_intent import parse_reminder
from src.live_conversation import LiveConversation
from src.sarvam_conversation import RecognizedTurn
from src.character_profile import CharacterProfile

class ChatCameraReminderTests(unittest.TestCase):
    def setUp(self):
        parent=PROJECT_ROOT/'runtime'/'chat-camera-tests'; parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent); self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)

    def test_preview_publishes_while_analysis_is_still_loading(self):
        camera=WebcamCapture(); entered=threading.Event(); ready=threading.Event()
        def slow_analysis():
            entered.set(); ready.wait(2)
        camera._analyze_frames=slow_analysis
        cap=Mock(); cap.isOpened.return_value=True
        cap.read.return_value=(True,np.zeros((10,10,3),dtype=np.uint8))
        with patch('src.webcam.cv2.VideoCapture',return_value=cap):
            try:
                camera.start(); self.assertTrue(entered.wait(1))
                self.assertIsNotNone(camera.latest_frame)
                self.assertEqual(camera.status,'Camera on')
                self.assertEqual(camera.analysis_status,'Loading face analysis…')
            finally:
                camera.release(); ready.set(); camera._thread.join(2)
        self.assertFalse(camera._thread.is_alive()); cap.release.assert_called_once()

    def test_one_time_reminder_is_durable_and_does_not_repeat_after_done(self):
        reminders=LocalReminders(self.folder/'reminders.sqlite')
        row=reminders.create_once('drink water',300,now=100)
        reminders=LocalReminders(reminders.path)
        self.assertEqual(reminders.due(now=399),[])
        self.assertEqual(len(reminders.due(now=400)),1)
        self.assertTrue(reminders.ack(row['id'],'done',now=401))
        self.assertEqual(reminders.due(now=10000),[])
        self.assertFalse(reminders.get(row['id'])['enabled'])

    def test_parser_only_accepts_explicit_bounded_request(self):
        self.assertEqual(parse_reminder('Remind me to drink water in the next five minutes.'),('drink water',300))
        self.assertEqual(parse_reminder('Please remind me to stretch in 2 hours'),('stretch',7200))
        self.assertIsNone(parse_reminder('What if I remind me to drink water in five minutes?'))
        self.assertIsNone(parse_reminder('remind me to stretch in zero minutes'))

    def client(self):
        client=LiveConversation('test',memory_path=self.folder/'memory.sqlite',transport=httpx.MockTransport(lambda r: httpx.Response(500)))
        client.profile=CharacterProfile({'name':'Amma','permissions':{'timers':True,'camera':True}})
        self.addCleanup(client.close)
        return client

    def test_spoken_and_typed_reply_path_saves_real_reminder_without_model(self):
        client=self.client()
        answer=client.reply(RecognizedTurn('remind me to drink water in five minutes','en-IN',None,False))
        self.assertIn('saved in Reminders',answer)
        self.assertEqual(client.reminders.list()[0]['title'],'drink water')
        self.assertEqual(client.reminders.list()[0]['one_shot'],1)
        self.assertEqual(len(client.memory.recent()),2)

    def test_new_chat_preserves_old_session_and_archive(self):
        client=self.client(); old=client.session.session_id
        client.reply(RecognizedTurn('remind me to stretch in one minute','en-IN',None,False))
        new=client.start_new_chat(); self.assertNotEqual(old,new)
        self.assertEqual(client.memory.recent(session=new),[])
        self.assertEqual(len(client.memory.recent(session=old)),2)
        self.assertEqual(client.memory.sessions()[0]['session'],old)

    def test_camera_command_respects_permission_and_requests_preview(self):
        client=self.client(); client.camera_request=Mock()
        client.reply(RecognizedTurn('open the camera','en-IN',None,False))
        client.camera_request.assert_called_once()
        client.profile.data['permissions']['camera']=False
        client.reply(RecognizedTurn('open the camera','en-IN',None,False))
        client.camera_request.assert_called_once()

    def test_camera_affirmative_only_confirms_a_current_pending_action(self):
        client=self.client(); client.camera_request=Mock()
        client.reply(RecognizedTurn('yes','en-IN',None,False))
        client.camera_request.assert_not_called()
