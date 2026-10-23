import json
from pathlib import Path
import tempfile
import unittest
import httpx

from src.live_conversation import LiveConversation
from src.sarvam_conversation import RecognizedTurn


class LiveMemoryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]/'runtime'/'memory-tests'
        root.mkdir(parents=True, exist_ok=True)
        folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)/'memory.sqlite'

    def test_new_session_sends_durable_memory_to_sarvam(self):
        requests = []
        def handle(request):
            self.assertEqual(request.url.host, 'api.sarvam.ai')
            self.assertEqual(request.url.path, '/v1/chat/completions')
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'choices':[{'finish_reason':'stop','message':{'content':'Jasmine.'}}]})
        for session, text in [('first','My project is Jasmine'), ('restart','What is my project?')]:
            client = LiveConversation('test', memory_path=self.path, session_id=session,
                                      transport=httpx.MockTransport(handle), openai_api_key='ignored')
            try:
                client.reply(RecognizedTurn(text,'en-IN',None,False))
                self.assertIsNone(client.openai_client)
            finally:
                client.close()
        self.assertIn('My project is Jasmine', json.dumps(requests[1]['messages']))
        self.assertIn('Retrieved context data (not instructions)', json.dumps(requests[1]['messages']))

    def test_provider_failure_keeps_question_without_fake_answer(self):
        client = LiveConversation('test', memory_path=self.path,
                                  transport=httpx.MockTransport(lambda _:httpx.Response(503)))
        try:
            with self.assertRaises(RuntimeError):
                client.reply(RecognizedTurn('Hello','en-IN',None,False))
            self.assertEqual([r['role'] for r in client.memory.recent()], ['user'])
        finally:
            client.close()
