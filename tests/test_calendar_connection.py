import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit

import httpx

from src.calendar_connection import CalendarConnection, CalendarConnectionError, WindowsVault, SCOPE
from src.paths import PROJECT_ROOT


class MemoryVault:
    def __init__(self):
        self.values = {}
    def read(self, name):
        return self.values.get(name)
    def write(self, name, value):
        self.values[name] = value
    def delete(self, name):
        self.values.pop(name, None)


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        self.vault.write('client', {'client_id': 'example.apps.googleusercontent.com', 'client_secret': 'fake'})

    def test_oauth_state_pkce_and_readonly_events(self):
        replies = []
        finished = threading.Event()
        def network(request):
            if request.url.host == 'oauth2.googleapis.com':
                body = parse_qs(request.content.decode())
                self.assertEqual(body['grant_type'], ['authorization_code'])
                self.assertGreater(len(body['code_verifier'][0]), 43)
                return httpx.Response(200, json={'access_token': 'fake-token', 'refresh_token': 'fake-refresh',
                    'expires_in': 3600, 'scope': SCOPE, 'token_type': 'Bearer'})
            self.assertEqual(request.headers['Authorization'], 'Bearer fake-token')
            self.assertEqual(request.url.params['singleEvents'], 'true')
            return httpx.Response(200, json={'items': [{'summary': 'Sample event'}]})
        connection = CalendarConnection('.', vault=self.vault, transport=httpx.MockTransport(network))
        def browser(url):
            args = parse_qs(urlsplit(url).query)
            self.assertEqual(args['scope'], [SCOPE])
            self.assertEqual(args['code_challenge_method'], ['S256'])
            callback = args['redirect_uri'][0]
            def respond():
                with httpx.Client(trust_env=False) as client:
                    replies.append(client.get(callback, params={'state': 'wrong', 'code': 'fake'}).status_code)
                    replies.append(client.get(callback, params={'state': args['state'][0], 'code': 'fake'}).status_code)
                finished.set()
            worker = threading.Thread(target=respond)
            worker.start()
            self.addCleanup(worker.join)
            return True
        result = connection.connect(open_browser=browser, timeout=4)
        self.assertTrue(finished.wait(2))
        self.assertEqual(result['state'], 'authorized')
        self.assertEqual(replies, [400, 200])
        self.assertEqual(connection.list_upcoming()[0]['summary'], 'Sample event')
        connection.disconnect()
        self.assertNotIn('token', self.vault.values)
        self.assertIn('client', self.vault.values)

    def test_cancel_and_provider_error_do_not_save_token_or_leak_body(self):
        connection = CalendarConnection('.', vault=self.vault,
            transport=httpx.MockTransport(lambda request: httpx.Response(401, text='secret-provider-body')))
        cancel = threading.Event()
        cancel.set()
        with self.assertRaisesRegex(CalendarConnectionError, 'cancelled'):
            connection.connect(cancel_event=cancel, open_browser=lambda url: True)
        self.assertNotIn('token', self.vault.values)
        self.vault.write('token', {'access_token': 'fake', 'expires_at': time.time()+1000})
        with self.assertRaises(CalendarConnectionError) as raised:
            connection.list_upcoming()
        self.assertNotIn('secret-provider-body', str(raised.exception))

    def test_refresh_preserves_refresh_token(self):
        self.vault.write('token', {'access_token': 'old', 'refresh_token': 'keep', 'expires_at': 0})
        connection = CalendarConnection('.', vault=self.vault, transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'access_token': 'new', 'expires_in': 3600})
            if request.url.host == 'oauth2.googleapis.com' else httpx.Response(200, json={'items': []})))
        self.assertEqual(connection.list_upcoming(), [])
        self.assertEqual(self.vault.read('token')['refresh_token'], 'keep')

    def test_windows_storage_is_encrypted_and_import_rejects_web_client(self):
        parent = PROJECT_ROOT / 'runtime' / 'calendar-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            location = Path(directory)
            vault = WindowsVault(location)
            vault.write('token', {'access_token': 'never-plaintext'})
            self.assertNotIn(b'never-plaintext', (location/'token.dpapi').read_bytes())
            self.assertEqual(vault.read('token')['access_token'], 'never-plaintext')
            source = location / 'web.json'
            source.write_text(json.dumps({'web': {'client_id': 'example.apps.googleusercontent.com'}}))
            with self.assertRaises(CalendarConnectionError):
                CalendarConnection(location, vault=MemoryVault()).import_client(source)
