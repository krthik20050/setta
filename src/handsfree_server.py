"""Loopback-only hands-free bridge: browser AEC/VAD, Groq tools, streamed clone PCM."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time

from .live_conversation import LiveConversation
from .manglish import to_manglish
from .paths import PROJECT_ROOT, MOTHER_ARTWORK_DIR, RUNTIME_DIR
from .desktop_activity import desktop_question
from .screen_context import describe_shared_window


class HandsfreeServer:
    def __init__(self, key, observations=lambda:[], camera_frame=None, port=8770, on_active=None):
        self.conversation = LiveConversation(key, observations=observations,camera_frame=camera_frame)
        self.token = secrets.token_urlsafe(32)
        self.on_active = on_active or (lambda active: None)
        self.origin = f'http://127.0.0.1:{port}'
        self._turn_lock = threading.Lock()
        self._ack_lock = threading.Lock()
        self._unacknowledged = {}
        self._journal_ids = {}
        self._latest_turn = 0
        self._screens = {}
        self._capacity = threading.BoundedSemaphore(3)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass  # Request bodies, tokens and transcripts are never logged.

            def _authorized(self):
                return (self.headers.get('Host') == self.server.server_name_for_origin and
                        self.headers.get('Origin') == owner.origin and
                        secrets.compare_digest(self.headers.get('X-Amma-Token',''),owner.token))

            def do_GET(self):
                if self.headers.get('Host') != self.server.server_name_for_origin:
                    self.send_error(403); return
                if self.path == '/':
                    data=(PROJECT_ROOT/'src/handsfree.html').read_text(encoding='utf-8').replace('__AMMA_TOKEN__',owner.token).encode()
                    content='text/html; charset=utf-8'
                elif self.path == '/character.png':
                    data=(MOTHER_ARTWORK_DIR/'mother-conversation-v10.png').read_bytes(); content='image/png'
                else:
                    self.send_error(404); return
                self.send_response(200)
                self.send_header('Content-Type',content)
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Frame-Options','DENY')
                self.send_header('Referrer-Policy','no-referrer')
                self.end_headers(); self.wfile.write(data)

            def do_POST(self):
                if not self._authorized():
                    # Drain only a tiny bounded body before closing, otherwise
                    # Windows can reset the socket before the 403 is received.
                    try:
                        length = int(self.headers.get('Content-Length','0'))
                        if 0 < length <= 8192:
                            self.connection.settimeout(1)
                            self.rfile.read(length)
                    except (ValueError, OSError):
                        pass
                    self.send_error(403); return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= 2_000_000:
                        raise ValueError('Audio request is too large or empty')
                    body=json.loads(self.rfile.read(length))
                except (ValueError,TypeError):
                    self.send_error(400); return
                if self.path == '/ack':
                    owner.acknowledge(str(body.get('turn_id','')))
                    self.send_response(204); self.end_headers(); return
                if self.path == '/screen':
                    try:
                        image=base64.b64decode(body.get('jpeg',''),validate=True)
                        if len(image)>1_000_000:raise ValueError('Image too large')
                        with owner._ack_lock:
                            pending=owner._screens.get(str(body.get('turn_id','')))
                            if pending:
                                pending['jpeg']=image; pending['ready'].set()
                    except (ValueError,TypeError):
                        self.send_error(400); return
                    self.send_response(204); self.end_headers(); return
                if self.path in {'/activate','/deactivate'}:
                    owner.on_active(self.path == '/activate')
                    self.send_response(204); self.end_headers(); return
                if self.path == '/cancel':
                    owner.invalidate()
                    self.send_response(204); self.end_headers(); return
                if self.path != '/turn':
                    self.send_error(404); return
                try:
                    audio=base64.b64decode(body.get('audio',''),validate=True)
                    if not 44 <= len(audio) <= 1_500_000:
                        raise ValueError('Invalid audio size')
                except (ValueError,TypeError):
                    self.send_error(400); return
                if not owner._capacity.acquire(blocking=False):
                    self.send_error(429); return
                ticket=owner.invalidate()
                def emit(event):
                    self.wfile.write((json.dumps(event,ensure_ascii=False)+'\n').encode())
                    self.wfile.flush()
                try:
                    self.send_response(200)
                    self.send_header('Content-Type','application/x-ndjson')
                    self.send_header('Cache-Control','no-store')
                    self.send_header('Connection','close')
                    self.end_headers()
                    self.close_connection=True
                    owner.process(audio,ticket,emit,body.get('window_shared') is True,body.get('capture_limit') is True)
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
                    owner.interrupted(str(ticket))

                except Exception as exc:
                    # Provider bodies can contain credentials; never echo them.
                    from .reply_errors import ReplyProviderError
                    message = str(exc) if isinstance(exc, ReplyProviderError) else 'This turn could not finish. Please try again; hands-free mode is still listening.'
                    try: emit({'type':'error','message':message})
                    except (OSError,ValueError): pass
                    owner.interrupted(str(ticket))
                finally:
                    owner._capacity.release()

        try:
            self.http = ThreadingHTTPServer(('127.0.0.1',port),Handler)
        except OSError:
            self.conversation.close()
            raise
        self.http.daemon_threads = True
        self.http.server_name_for_origin = f'127.0.0.1:{self.http.server_port}'
        self.origin = f'http://127.0.0.1:{self.http.server_port}'

    def start(self):
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        return self.origin

    def invalidate(self):
        with self._ack_lock:
            self._latest_turn += 1
            return self._latest_turn

    def acknowledge(self, ticket):
        with self._ack_lock:
            self._unacknowledged.pop(ticket,None)
            journal_turn = self._journal_ids.pop(ticket,None)
        if journal_turn:
            self.conversation.journal.event(journal_turn, 'browser_playback_completed')

    def interrupted(self, ticket):
        with self._ack_lock:
            message = self._unacknowledged.pop(ticket,None)
            journal_turn = self._journal_ids.pop(ticket,None)
        if journal_turn:
            self.conversation.journal.event(journal_turn, 'browser_turn_interrupted')
        if message:
            self.conversation.memory.delete_message(message)

    def process(self, audio, ticket, emit, window_shared=False, capture_limit=False):
        with self._turn_lock:
            if ticket != self._latest_turn: return
            # A new turn removes prior replies that the browser did not finish
            # playing. Do not pretend the user heard unplayed generated text.
            with self._ack_lock:
                old = list(self._unacknowledged.values()); self._unacknowledged.clear()
                old_journals = list(self._journal_ids.values()); self._journal_ids.clear()
            for journal_turn in old_journals:
                self.conversation.journal.event(journal_turn, 'superseded_without_playback_ack')
            for identity in old:
                self.conversation.memory.delete_message(identity)
            started=time.monotonic()
            turn=self.conversation.recognize(audio)
            recognition_seconds=time.monotonic()-started
            if not turn or ticket != self._latest_turn: return
            with self._ack_lock:
                self._journal_ids[str(ticket)] = self.conversation.journal_turn
            emit({'type':'transcript','text':to_manglish(turn.text),'turn_id':str(ticket)})
            if capture_limit:
                self.conversation.journal.event(self.conversation.journal_turn, 'capture_limit', seconds=27)
                emit({'type':'error','message':'The 27-second recording limit was reached. Your captured audio was saved; please split this into shorter turns so Amma does not answer an unfinished sentence.'})
                return
            self.conversation.shared_window_observations=[]
            if window_shared and desktop_question(turn.text):
                pending={'ready':threading.Event(),'jpeg':None}
                with self._ack_lock:self._screens[str(ticket)]=pending
                try:
                    emit({'type':'screen_request','turn_id':str(ticket)})
                    pending['ready'].wait(4)
                    if ticket != self._latest_turn:return
                    settings=self.conversation.profile.data.get('context',{})
                    self.conversation.shared_window_observations=[describe_shared_window(
                        self.conversation.groq_client,settings.get('vision_model','qwen/qwen3.8-27b'),pending['jpeg'])]
                finally:
                    with self._ack_lock:self._screens.pop(str(ticket),None)
            self.conversation.agent_tools.cancelled = lambda: ticket != self._latest_turn
            try:
                reply=self.conversation.reply(turn)
            finally:
                self.conversation.shared_window_observations=[]
            reply_ready=time.monotonic()-started
            last=self.conversation.memory.recent(1,self.conversation.session.session_id)
            if last and last[-1]['role']=='assistant':
                with self._ack_lock:
                    self._unacknowledged[str(ticket)] = last[-1]['id']
            if ticket != self._latest_turn:
                self.interrupted(str(ticket)); return
            emit({'type':'reply','text':to_manglish(reply),'turn_id':str(ticket)})
            first=True
            for chunk in self.conversation.stream_speech(reply,turn):
                if ticket != self._latest_turn:
                    self.interrupted(str(ticket)); return
                emit({'type':'audio','pcm':base64.b64encode(chunk).decode(), 'sample_rate':24000,
                      'turn_id':str(ticket),'first_audio_seconds':round(time.monotonic()-started,3) if first else None})
                if first:
                    RUNTIME_DIR.mkdir(parents=True,exist_ok=True)
                    (RUNTIME_DIR/'handsfree-latency.json').write_text(json.dumps({
                        'recognition_seconds':round(recognition_seconds,3),
                        'reply_and_tools_seconds':round(reply_ready-recognition_seconds,3),
                        'first_pcm_after_upload_seconds':round(time.monotonic()-started,3),
                        'scope':'Server-side readiness; excludes speech capture, browser buffering and hardware output.'
                    },indent=2),encoding='utf-8')
                first=False
            if first:
                raise ValueError('No streamed audio was returned')
            emit({'type':'done','turn_id':str(ticket)})

    def stop(self):
        self.invalidate()
        self.http.shutdown(); self.http.server_close()
        # In-flight HTTP work owns its client until it releases the turn lock.
        def close_when_idle():
            with self._turn_lock:
                self.conversation.close()
        threading.Thread(target=close_when_idle,daemon=True).start()
