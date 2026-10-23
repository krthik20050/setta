from datetime import datetime
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx

from src.decision_router import decide
from src.live_conversation import LiveConversation
from src.sarvam_conversation import RecognizedTurn
from src.laya_shadow import LayaShadow


class DecisionRouterTests(unittest.TestCase):
    def test_clock_uses_supplied_local_time(self):
        answer = decide('What time is it?', 'en-IN', now=datetime(2026, 10, 21, 14, 30))
        self.assertEqual(answer.answer, 'It is 2:30 PM.')

    def test_profile_requires_saved_name_and_whole_query(self):
        self.assertIsNone(decide('What is my name?', 'en-IN').answer)
        facts = [{'key': 'user_name', 'value': 'Karthik'}]
        self.assertEqual(decide('What is my name?', 'en-IN', facts).answer, 'Your name is Karthik.')
        self.assertIsNone(decide('What is my name in Hindi?', 'en-IN', facts).answer)
        self.assertIsNone(decide('What is my name?', 'hi-IN', facts).answer)
        self.assertIsNone(decide('What is my name?', 'en-IN', [{'key':'user_name','value':'x'*1000}]).answer)

    def test_local_reply_skips_provider_but_preserves_archive_and_memory(self):
        def forbidden(request):
            self.fail('Local clock answer must not call the reply provider')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            with patch.dict(os.environ, {'LAYA_SHADOW':'0'}):
                client = LiveConversation('test', memory_path=Path(folder)/'memory.sqlite',
                    transport=httpx.MockTransport(forbidden), groq_api_key='', reply_provider='sarvam')
            try:
                answer = client.reply(RecognizedTurn('What time is it?', 'en-IN', None, False))
                self.assertTrue(answer.startswith('It is '))
                rows = client.memory.recent()
                self.assertEqual([r['role'] for r in rows], ['user', 'assistant'])
                self.assertEqual(rows[-1]['text'], answer)
            finally:
                client.close()

    def test_shadow_default_off_does_not_start_process(self):
        with patch.dict(os.environ, {'LAYA_SHADOW':'0'}):
            shadow = LayaShadow()
        with patch('src.laya_shadow.subprocess.Popen') as process:
            shadow.submit('Open an app', 'en-IN', None, 'test', 'reply_model')
            process.assert_not_called()
        shadow.close()

    def test_shadow_submission_never_waits_for_inference(self):
        import threading
        from unittest.mock import Mock
        journal = Mock()
        with patch.dict(os.environ, {'LAYA_SHADOW':'1'}):
            shadow = LayaShadow()
        # A worker already running can be busy indefinitely; submit only queues.
        shadow.worker = threading.Thread()
        shadow.submit('Hello', 'en-IN', journal, 'one', 'reply_model')
        shadow.submit('Hello again', 'en-IN', journal, 'two', 'reply_model')
        journal.event.assert_called_once_with('two', 'decision_shadow_skipped', reason='worker_busy')
        shadow.worker = None
        shadow.close()
