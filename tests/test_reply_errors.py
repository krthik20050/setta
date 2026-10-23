import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from src.reply_errors import groq_error


class ReplyErrorTests(unittest.TestCase):
    def test_token_limit_is_actionable_without_leaking_provider_body(self):
        with tempfile.TemporaryDirectory() as directory, patch('src.reply_errors.RUNTIME_DIR', Path(directory)):
            response = httpx.Response(429, headers={'retry-after': '8'}, json={'error': {
                'type': 'tokens', 'message': 'secret-credential tokens per minute'}})
            error = groq_error(response, 'test-model')
            self.assertIn('per-minute token limit', str(error))
            self.assertIn('8 seconds', str(error))
            stored = (Path(directory)/'reply-provider-error.json').read_text()
            self.assertNotIn('secret-credential', stored + str(error))
            self.assertEqual(json.loads(stored)['status'], 429)

    def test_authentication_is_not_reported_as_quota(self):
        with tempfile.TemporaryDirectory() as directory, patch('src.reply_errors.RUNTIME_DIR', Path(directory)):
            self.assertIn('rejected the API key', str(groq_error(httpx.Response(401), 'test')))
