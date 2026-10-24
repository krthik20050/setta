import json
from pathlib import Path
import tempfile
import time
import unittest
import httpx

from src.character_profile import CharacterProfile
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
                                      transport=httpx.MockTransport(handle), openai_api_key='', groq_api_key='')
            try:
                client.reply(RecognizedTurn(text,'en-IN',None,False))
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

    def test_chat_preference_requires_consent_and_applies_to_current_reply(self):
        profile_path = self.path.parent/'amma.json'
        profile_path.write_text(json.dumps({'name': 'Amma', 'role': 'companion',
            'personalization': {'reply_length': 'balanced', 'advice_style': 'ask_first',
                'humor': 'occasional', 'follow_up': 'only_when_needed'}}), encoding='utf-8')
        requests = []
        def handle(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'choices':[{'finish_reason':'stop',
                'message':{'content':'Photosynthesis uses light to make food.'}}]})
        client = LiveConversation('test', memory_path=self.path,
            transport=httpx.MockTransport(handle), openai_api_key='', groq_api_key='', reply_provider='sarvam')
        client.profile = CharacterProfile.load(profile_path)
        try:
            first = client.reply(RecognizedTurn('Could you be more detailed?', 'en-IN', None, False))
            self.assertIn('this reply', first)
            self.assertIn('default', first)
            self.assertEqual(client.profile.personalization()['reply_length'], 'balanced')
            declined = client.reply(RecognizedTurn('no', 'en-IN', None, False))
            self.assertIn('that reply', declined)
            self.assertEqual(client.profile.personalization()['reply_length'], 'balanced')
            client._pending_personality = {'values': {'reply_length': 'brief'},
                'language': 'en-IN', 'expires_at': time.monotonic()-1}
            expired = client.reply(RecognizedTurn('yes', 'en-IN', None, False))
            self.assertIn('pending action', expired)
            self.assertEqual(client.profile.personalization()['reply_length'], 'balanced')

            embedded = client.reply(RecognizedTurn('Explain this briefly: photosynthesis', 'en-IN', None, False))
            self.assertIn('Would you like me to make that your default?', embedded)
            self.assertIn('very brief replies', json.dumps(requests[0]['messages']))
            self.assertEqual(client.profile.personalization()['reply_length'], 'balanced')
            saved = client.reply(RecognizedTurn('yes', 'en-IN', None, False))
            self.assertIn('saved', saved)
            self.assertEqual(CharacterProfile.load(profile_path).personalization()['reply_length'], 'brief')
            self.assertEqual(len(requests), 1)
        finally:
            client.close()

    def test_explicit_chat_preference_saves_without_calling_reply_provider(self):
        profile_path = self.path.parent/'amma-explicit.json'
        profile_path.write_text(json.dumps({'name': 'Amma', 'role': 'companion'}), encoding='utf-8')
        client = LiveConversation('test', memory_path=self.path,
            transport=httpx.MockTransport(lambda _: self.fail('A preference command should be handled locally')),
            openai_api_key='', groq_api_key='', reply_provider='sarvam')
        client.profile = CharacterProfile.load(profile_path)
        try:
            answer = client.reply(RecognizedTurn('From now on, keep it brief.', 'en-IN', None, False))
            self.assertIn('saved', answer)
            self.assertEqual(CharacterProfile.load(profile_path).personalization()['reply_length'], 'brief')
        finally:
            client.close()

    def test_detailed_profile_allows_a_longer_voice_reply(self):
        profile_path = self.path.parent/'amma-detailed.json'
        profile_path.write_text(json.dumps({'name': 'Amma', 'role': 'companion',
            'personalization': {'reply_length': 'detailed', 'advice_style': 'ask_first',
                'humor': 'off', 'follow_up': 'only_when_needed'}}), encoding='utf-8')
        requests = []
        def handle(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={'choices':[{'finish_reason':'stop',
                'message':{'content':'First useful detail. Second useful detail. Third useful detail.'}}]})
        client = LiveConversation('test', memory_path=self.path,
            transport=httpx.MockTransport(handle), openai_api_key='', groq_api_key='', reply_provider='sarvam')
        client.profile = CharacterProfile.load(profile_path)
        try:
            answer = client.reply(RecognizedTurn('Explain this topic.', 'en-IN', None, False))
            self.assertEqual(answer.count('.'), 3)
            self.assertIn('no more than 90 words', requests[0]['messages'][0]['content'])
        finally:
            client.close()
