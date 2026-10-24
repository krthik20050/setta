import json
import os
import unittest
from unittest.mock import Mock, patch

import httpx

from src.sarvam_conversation import RecognizedTurn, SarvamConversation

ENV = {'OPENAI_MODEL': 'gpt-4.1-mini', 'OPENAI_DEEP_MODEL': 'gpt-4.1',
       'GROQ_MODEL': 'openai/gpt-oss-20b', 'REPLY_PROVIDER': '',
       'OMNIROUTE_API_KEY': '', 'SARVAM_REPLY_FALLBACK': '0'}


def ok(text='Okay.', finish='stop'):
    return httpx.Response(200, json={'choices': [{'finish_reason': finish, 'message': {'content': text}}]})


def turn(text, language='en-IN'):
    return RecognizedTurn(text, language, None, False)


class TieredReplyTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def conversation(self, handler, groq='fake-groq'):
        def record(request):
            body = json.loads(request.content) if request.content else {}
            self.calls.append((request.url.host, body.get('model')))
            return handler(request, body)
        c = SarvamConversation('fake-sarvam', transport=httpx.MockTransport(record),
                               openai_api_key='fake-openai', groq_api_key=groq)
        self.addCleanup(c.close)
        return c

    def test_openai_key_selects_auto_and_small_talk_uses_fast_model(self):
        def handler(request, body):
            self.assertEqual(request.url.path, '/v1/chat/completions')
            self.assertEqual(request.headers['authorization'], 'Bearer fake-openai')
            self.assertFalse(body['store'])
            self.assertIn('English', body['messages'][0]['content'])
            return ok('Hello dear.')
        c = self.conversation(handler)
        self.assertEqual(c.reply_provider, 'auto')
        self.assertEqual(c.reply(turn('Hello')), 'Hello dear.')
        self.assertEqual(self.calls, [('api.openai.com', 'gpt-4.1-mini')])
        self.assertEqual((c.last_route['tier'], c.last_route['provider'], c.last_route['model']),
                         ('fast', 'openai', 'gpt-4.1-mini'))

    def test_reasoning_request_uses_deep_model(self):
        c = self.conversation(lambda request, body: ok('Light scatters.'))
        c.reply(turn('Explain why the sky is blue'))
        self.assertEqual(self.calls, [('api.openai.com', 'gpt-4.1')])
        self.assertEqual(c.last_route['tier'], 'deep')
        self.assertEqual(c.last_route['reason'], 'reasoning_keyword')

    def test_openai_rate_limit_falls_back_to_groq_and_cools_down(self):
        def handler(request, body):
            if request.url.host == 'api.openai.com':
                return httpx.Response(429, headers={'retry-after': '20'}, text='fake-openai secret')
            return ok('From Groq.')
        c = self.conversation(handler)
        self.assertEqual(c.reply(turn('Hello')), 'From Groq.')
        self.assertEqual(c.last_route['provider'], 'groq')
        self.calls.clear()
        c.reply(turn('Hello again'))
        self.assertEqual([host for host, _ in self.calls], ['api.groq.com'])

    def test_openai_network_error_falls_back_to_groq(self):
        def handler(request, body):
            if request.url.host == 'api.openai.com':
                raise httpx.ConnectError('offline', request=request)
            return ok('From Groq.')
        c = self.conversation(handler)
        self.assertEqual(c.reply(turn('Hello')), 'From Groq.')

    def test_unavailable_deep_model_falls_back_to_fast_openai_model(self):
        def handler(request, body):
            if body['model'] == 'gpt-4.1':
                return httpx.Response(404)
            return ok('Fast answer.')
        c = self.conversation(handler)
        self.assertEqual(c.reply(turn('Compare tea and coffee')), 'Fast answer.')
        self.assertEqual(self.calls, [('api.openai.com', 'gpt-4.1'), ('api.openai.com', 'gpt-4.1-mini')])
        self.assertEqual(c.last_route['model'], 'gpt-4.1-mini')

    def test_incomplete_fast_reply_escalates_to_deep_model(self):
        def handler(request, body):
            return ok('partial', finish='length') if body['model'] == 'gpt-4.1-mini' else ok('Complete answer.')
        c = self.conversation(handler)
        self.assertEqual(c.reply(turn('Hello')), 'Complete answer.')
        self.assertEqual(self.calls, [('api.openai.com', 'gpt-4.1-mini'), ('api.openai.com', 'gpt-4.1')])
        self.assertTrue(c.last_route['escalated'])
        self.assertEqual(c.last_route['tier'], 'deep')

    def test_wrong_language_retry_escalates_to_deep_model(self):
        def handler(request, body):
            return ok('Hello there.') if body['model'] == 'gpt-4.1-mini' else ok('നമസ്കാരം.')
        c = self.conversation(handler)
        self.assertEqual(c.reply(turn('ഹലോ', 'ml-IN')), 'നമസ്കാരം.')
        self.assertEqual([model for _, model in self.calls], ['gpt-4.1-mini', 'gpt-4.1'])

    def test_openai_runs_tool_loop_once_per_action(self):
        execute = Mock(return_value={'status': 'ok', 'result': '4'})
        tools = Mock(schemas=[{'type': 'function', 'function': {'name': 'calculate', 'parameters': {'type': 'object'}}}],
                     execute=execute)
        def handler(request, body):
            self.assertEqual(body['tools'], tools.schemas)
            if not any(m.get('role') == 'tool' for m in body['messages']):
                return httpx.Response(200, json={'choices': [{'finish_reason': 'tool_calls', 'message': {
                    'role': 'assistant', 'tool_calls': [{'id': 'c1', 'type': 'function',
                    'function': {'name': 'calculate', 'arguments': '{"expression":"2+2"}'}}]}}]})
            return ok('It is four.')
        c = self.conversation(handler)
        c.agent_tools = tools
        self.assertEqual(c.reply(turn('What is 2 plus 2')), 'It is four.')
        execute.assert_called_once()
        self.assertEqual([host for host, _ in self.calls], ['api.openai.com', 'api.openai.com'])

    def test_all_providers_failing_raises_sanitized_error(self):
        c = self.conversation(lambda request, body: httpx.Response(503, text='fake-openai fake-groq private'))
        with self.assertRaises(RuntimeError) as caught:
            c.reply(turn('Hello'))
        self.assertNotIn('fake-', str(caught.exception))
        self.assertEqual([host for host, _ in self.calls], ['api.openai.com', 'api.groq.com'])
        self.assertEqual(c.history, [])

    def test_without_groq_key_auto_uses_openai_only(self):
        c = self.conversation(lambda request, body: httpx.Response(500), groq='')
        with self.assertRaises(RuntimeError):
            c.reply(turn('Hello'))
        self.assertEqual([host for host, _ in self.calls], ['api.openai.com'])


if __name__ == '__main__':
    unittest.main()
