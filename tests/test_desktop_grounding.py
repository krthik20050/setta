import json
from pathlib import Path
import tempfile
import time
import unittest
import httpx
from src.live_conversation import LiveConversation
from src.companion_context import Observation
from src.sarvam_conversation import RecognizedTurn


class DesktopGroundingTests(unittest.TestCase):
    def test_old_assistant_guess_is_not_evidence_for_current_desktop_question(self):
        def handle(request):
            body = json.loads(request.content)
            messages = json.dumps(body['messages'], ensure_ascii=False)
            self.assertIn('Codex.exe', messages)
            self.assertNotIn('You were writing a Python script', messages)
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop',
                'message':{'content':'Codex is active. I cannot tell the exact task from the app name alone.'}}]})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'runtime') as folder:
            client = LiveConversation('test', memory_path=Path(folder)/'memory.sqlite',
                observations=lambda:[Observation('foreground_app','Codex.exe','windows',1,time.monotonic())],
                transport=httpx.MockTransport(handle), groq_api_key='', reply_provider='sarvam')
            try:
                client.memory.add_message('old','assistant','You were writing a Python script.')
                client.reply(RecognizedTurn('What was I working on?', 'en-IN',None,False))
            finally:
                client.close()
