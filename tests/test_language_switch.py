import json
import unittest
import httpx
from src.sarvam_conversation import SarvamConversation, RecognizedTurn


class LanguageSwitchTests(unittest.TestCase):
    def test_malayalam_history_does_not_end_english_turn_on_first_mismatch(self):
        replies = iter(['\u0d36\u0d30\u0d3f, \u0d2a\u0d31\u0d2f\u0d42.', 'Sure. What happened today?'])
        calls = []
        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [{'finish_reason':'stop',
                'message': {'content': next(replies)}}]})
        client = SarvamConversation('test', openai_api_key='', groq_api_key='test',
            reply_provider='groq', transport=httpx.MockTransport(handle))
        self.addCleanup(client.close)
        client.history = [{'role':'assistant','content':'\u0d2e\u0d4b\u0d28\u0d47, \u0d2a\u0d31\u0d2f\u0d42.'}]
        self.assertEqual(client.reply(RecognizedTurn('Can we talk in English?', 'en-IN', None, False)),
                         'Sure. What happened today?')
        self.assertEqual(len(calls), 2)
        self.assertEqual(client.history[-1]['content'], 'Sure. What happened today?')
