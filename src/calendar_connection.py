"""Read-only Google Calendar desktop OAuth with encrypted Windows persistence.

References: developers.google.com/identity/protocols/oauth2/native-app and
developers.google.com/workspace/calendar/api/auth. Call network methods in a worker.
"""
import base64
import ctypes
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

import httpx

SCOPE = 'https://www.googleapis.com/auth/calendar.events.readonly'
TOKEN_URL = 'https://oauth2.googleapis.com/token'


class CalendarConnectionError(RuntimeError):
    pass


class WindowsVault:
    """DPAPI current-user storage; never fall back to plaintext."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def _crypt(self, data, decrypt=False):
        if os.name != 'nt':
            raise CalendarConnectionError('Secure Windows credential storage is unavailable.')
        class Blob(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]
        buffer = ctypes.create_string_buffer(data)
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        output = Blob()
        crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        crypt.CryptProtectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_wchar_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
        crypt.CryptProtectData.restype = ctypes.c_int
        crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
        crypt.CryptUnprotectData.restype = ctypes.c_int
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        if decrypt:
            success = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
        else:
            success = crypt.CryptProtectData(ctypes.byref(source), 'Setta Calendar', None, None, None, 1, ctypes.byref(output))
        if not success:
            raise CalendarConnectionError('Windows could not unlock or protect Calendar credentials.')
        try:
            return ctypes.string_at(output.data, output.length)
        finally:
            kernel.LocalFree(output.data)

    def read(self, name):
        path = self.directory / (name + '.dpapi')
        if not path.exists():
            return None
        try:
            return json.loads(self._crypt(path.read_bytes(), True))
        except (OSError, ValueError):
            raise CalendarConnectionError('Saved Calendar credentials could not be read.') from None

    def write(self, name, value):
        encrypted = self._crypt(json.dumps(value).encode())
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / (name + '.dpapi')
        temporary = self.directory / (name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            temporary.write_bytes(encrypted)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def delete(self, name):
        (self.directory / (name + '.dpapi')).unlink(missing_ok=True)


class CalendarConnection:
    def __init__(self, directory, *, vault=None, transport=None):
        self.vault = vault or WindowsVault(directory)
        self.transport = transport
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._connecting = False

    def status(self):
        try:
            if self._connecting:
                return {'state': 'connecting', 'message': 'Finish signing in in your browser.'}
            if not self.vault.read('client'):
                return {'state': 'setup_required', 'message': 'Import a Google Desktop OAuth client JSON to connect.'}
            if not self.vault.read('token'):
                return {'state': 'disconnected', 'message': 'Ready to sign in to Google Calendar.'}
            return {'state': 'connected', 'message': 'Google Calendar credentials saved. Test to verify access.'}
        except CalendarConnectionError as exc:
            return {'state': 'unavailable', 'message': str(exc)}

    def import_client(self, path):
        try:
            path = Path(path)
            if path.stat().st_size > 65536:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8-sig'))['installed']
            client_id = data['client_id']
            secret = data.get('client_secret', '')
            if not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com'):
                raise ValueError()
            if not isinstance(secret, str):
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise CalendarConnectionError('Choose a valid Google OAuth client JSON for a Desktop app.') from None
        with self._lock:
            if self._connecting:
                raise CalendarConnectionError('Cancel the current sign-in before changing the client.')
            self.vault.write('client', {'client_id': client_id, 'client_secret': secret})
            self.vault.delete('token')
        return self.status()

    def _request(self, method, url, **kwargs):
        try:
            with httpx.Client(timeout=15, transport=self.transport, follow_redirects=False) as client:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                payload = response.json() if response.content else {}
                if not isinstance(payload, dict):
                    raise ValueError('Unexpected response')
                return payload
        except (httpx.HTTPError, ValueError):
            raise CalendarConnectionError('Google Calendar could not complete the request. Check sign-in and your connection.') from None

    def cancel(self):
        self._cancel.set()

    def connect(self, cancel_event=None, timeout=180, open_browser=None):
        """User-initiated, blocking OAuth. Invoke from a worker, not the UI thread."""
        timeout = min(600, max(1, float(timeout)))
        with self._lock:
            if self._connecting:
                raise CalendarConnectionError('Calendar sign-in is already running.')
            config = self.vault.read('client')
            if not config:
                raise CalendarConnectionError('Import a Google Desktop OAuth client JSON first.')
            self._connecting = True
            self._cancel.clear()
        server = None
        try:
            state = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(64)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
            result = {}
            class Handler(BaseHTTPRequestHandler):
                def setup(self):
                    self.request.settimeout(2)
                    super().setup()
                def log_message(self, *_):
                    pass
                def do_GET(self):
                    query = parse_qs(urlsplit(self.path).query)
                    if urlsplit(self.path).path != '/oauth/callback' or query.get('state') != [state]:
                        self.send_error(400, 'Invalid sign-in response'); return
                    if query.get('error'):
                        result['error'] = True
                    elif len(query.get('code', [])) == 1:
                        result['code'] = query['code'][0]
                    else:
                        self.send_error(400); return
                    body = b'You can close this tab and return to Setta.'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Referrer-Policy', 'no-referrer')
                    self.end_headers(); self.wfile.write(body)
            server = HTTPServer(('127.0.0.1', 0), Handler)
            server.timeout = .2
            redirect = f'http://127.0.0.1:{server.server_port}/oauth/callback'
            url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
                'client_id': config['client_id'], 'redirect_uri': redirect,
                'response_type': 'code', 'scope': SCOPE, 'state': state,
                'code_challenge': challenge, 'code_challenge_method': 'S256',
                'access_type': 'offline', 'prompt': 'consent'})
            if (open_browser or webbrowser.open)(url) is False:
                raise CalendarConnectionError('The browser could not open. Please try again.')
            deadline = time.monotonic() + timeout
            while not result:
                if self._cancel.is_set() or (cancel_event and cancel_event.is_set()):
                    raise CalendarConnectionError('Calendar sign-in cancelled.')
                if time.monotonic() >= deadline:
                    raise CalendarConnectionError('Calendar sign-in timed out. Please try again.')
                server.handle_request()
            if result.get('error'):
                raise CalendarConnectionError('Google Calendar permission was not granted.')
            token = self._request('POST', TOKEN_URL, data={**config,
                'grant_type': 'authorization_code', 'code': result['code'],
                'redirect_uri': redirect, 'code_verifier': verifier})
            self._save_token(token)
            return {'state': 'authorized', 'message': 'Google sign-in completed.'}
        except OSError:
            raise CalendarConnectionError('The local sign-in callback could not start.') from None
        finally:
            if server:
                server.server_close()
            self._connecting = False

    def _save_token(self, token, previous=None):
        if not token.get('access_token') or token.get('token_type', 'Bearer').lower() != 'bearer':
            raise CalendarConnectionError('Google did not return usable Calendar credentials.')
        if token.get('scope') and SCOPE not in token['scope'].split():
            raise CalendarConnectionError('Read-only Calendar permission was not granted.')
        value = {**(previous or {}), **token, 'expires_at': time.time() + float(token.get('expires_in', 3600))}
        if self._cancel.is_set():
            raise CalendarConnectionError('Calendar sign-in cancelled.')
        with self._lock:
            if self._cancel.is_set():
                raise CalendarConnectionError('Calendar sign-in cancelled.')
            self.vault.write('token', value)

    def _access_token(self):
        with self._lock:
            token = self.vault.read('token')
            if not token:
                raise CalendarConnectionError('Connect Google Calendar first.')
            if token.get('expires_at', 0) <= time.time() + 60:
                config = self.vault.read('client')
                if not config or not token.get('refresh_token'):
                    raise CalendarConnectionError('Google Calendar sign-in expired. Connect again.')
                fresh = self._request('POST', TOKEN_URL, data={**config,
                    'grant_type': 'refresh_token', 'refresh_token': token['refresh_token']})
                self._save_token(fresh, token)
                token = self.vault.read('token')
            return token['access_token']

    def list_upcoming(self, limit=10):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise CalendarConnectionError('Choose between 1 and 100 upcoming events.')
        payload = self._request('GET', 'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers={'Authorization': 'Bearer ' + self._access_token()}, params={
                'timeMin': datetime.now(timezone.utc).isoformat(), 'singleEvents': 'true',
                'orderBy': 'startTime', 'maxResults': limit})
        return payload.get('items', [])

    def test_connection(self):
        events = self.list_upcoming(1)
        return {'state': 'connected', 'message': 'Google Calendar access verified.', 'event_count': len(events)}

    def disconnect(self):
        self.cancel()
        with self._lock:
            self.vault.delete('token')
        return {'state': 'disconnected', 'message': 'Calendar disconnected locally. You can also revoke access in your Google Account.'}
