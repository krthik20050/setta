import json
import os
import unittest
from unittest.mock import patch
import httpx
from src.reply_fallback import ReplyFallback
from src.companion_context import CompanionContext


class FallbackTests(unittest.TestCase):
    def test_quota_switches_credentials_and_preserves_tool_messages(self):
        seen = []
        def handle(request):
            seen.append((request.url.host, request.headers['authorization'], json.loads(request.content)))
            if request.url.host == 'api.groq.com':
                return httpx.Response(429, headers={'retry-after': '8'})
            return httpx.Response(200, json={'choices': []})
        with patch.dict(os.environ, {'OMNIROUTE_API_KEY': 'gateway-only', 'OMNIROUTE_MODEL': 'tested-combo'}):
            router = ReplyFallback(httpx.MockTransport(handle))
            self.addCleanup(router.close)
            with httpx.Client(base_url='https://api.groq.com', headers={'Authorization': 'Bearer groq-only'}, transport=httpx.MockTransport(handle)) as primary:
                payload = {'model': 'primary', 'messages': [{'role': 'tool', 'tool_call_id': 'a', 'content': 'launch_requested'}], 'tools': [], 'reasoning_effort': 'low'}
                router.post(primary, payload)
                router.post(primary, payload)
            self.assertEqual([row[0] for row in seen], ['api.groq.com', '127.0.0.1', '127.0.0.1'])
            self.assertEqual(seen[1][1], 'Bearer gateway-only')
            self.assertEqual(seen[1][2]['messages'], payload['messages'])
            self.assertNotIn('reasoning_effort', seen[1][2])
            self.assertEqual(payload['model'], 'primary')

    def test_auth_failure_does_not_switch_provider(self):
        with patch.dict(os.environ, {'OMNIROUTE_API_KEY': 'test', 'OMNIROUTE_MODEL': 'model'}):
            router = ReplyFallback(httpx.MockTransport(lambda r: self.fail('No fallback on 401')))
            self.addCleanup(router.close)
            with httpx.Client(base_url='https://api.groq.com', transport=httpx.MockTransport(lambda r: httpx.Response(401))) as primary:
                self.assertEqual(router.post(primary, {}) .status_code, 401)

    def test_remote_gateway_rejected(self):
        with patch.dict(os.environ, {'OMNIROUTE_BASE_URL': 'https://untrusted.example/v1'}):
            with self.assertRaises(ValueError): ReplyFallback()

    def test_memory_is_not_duplicated_and_sources_remain(self):
        original = {'recent': [{'role': 'user', 'text': 'already in history'}],
                    'confirmed_facts': [{'value': 'likes short replies'}],
                    'observations': [{'source': 'clock', 'value': 'today'}]}
        message = CompanionContext.context_message(original)['content']
        self.assertNotIn('already in history', message)
        self.assertIn('likes short replies', message)
        self.assertIn('clock', message)
        self.assertIn('recent', original)
