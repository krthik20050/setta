"""Native Sarvam realtime input. Partials are display-only; finals own replies."""
import base64
from collections import deque
import json
import queue
import re
import threading
import time
from urllib.parse import urlencode

import speech_recognition as sr
from websockets.sync.client import connect
from websockets.exceptions import WebSocketException

from .sarvam_conversation import RecognizedTurn, mixed_malayalam


class TranscriptTurn:
    def __init__(self):
        self.segments = []
        self.partial = ''
        self.speaking = False
        self.deadline = None
        self.language = 'ml-IN'
        self.confidence = None

    @property
    def preview(self):
        return ' '.join(self.segments + ([self.partial] if self.partial else []))

    def accept(self, event, now):
        kind = event.get('event')
        if kind == 'vad.speech_start':
            self.speaking, self.deadline = True, None
        elif kind == 'vad.speech_end':
            self.speaking = False
        elif kind == 'transcript.partial':
            self.partial = str(event.get('text') or '').strip()
            if self.partial:
                self.speaking, self.deadline = True, None
        elif kind == 'transcript.final':
            text = str(event.get('text') or '').strip()
            self.partial = ''
            self.speaking = False
            if text and any(char.isalnum() for char in text):
                self.segments.append(text)
                self.language = event.get('language') or self.language
                self.confidence = event.get('language_confidence')
                # Heuristic patience, not a claim of semantic turn detection.
                unfinished = re.search(r'\b(and|but|because|to|the|a|my|going|wash|like|uh|um)\W*$', text, re.I)
                self.deadline = now + (1.5 if unfinished else .65)

    def ready(self, now):
        return bool(self.segments and not self.speaking and self.deadline is not None and now >= self.deadline)

    def recognized(self):
        text, language = self.preview, self.language
        if re.search(r'[\u0d00-\u0d7f]', text): language = 'ml-IN'
        elif re.search(r'[\u0900-\u097f]', text): language = 'hi-IN'
        if language not in {'ml-IN', 'hi-IN', 'en-IN'}:
            raise ValueError('Unsupported transcription language')
        return RecognizedTurn(text, language, self.confidence, mixed_malayalam(text))


def capture_turns(key, stop, playing, on_partial, on_speaking, on_status=lambda value:None):
    """Yield (PCM WAV-compatible AudioData, final turn), with bounded buffers.

    Suppresses microphone transport during playback plus a .5s speaker tail.
    This is half-duplex protection, not acoustic echo cancellation.
    """
    parameters = {'language_code':'auto', 'model':'saaras:v3-realtime',
        'stream_type':'fast', 'mode':'codemix', 'encoding':'linear16',
        'sample_rate':16000, 'endpointing':'vad', 'silence_duration_ms':2200,
        'min_speech_duration_ms':350, 'threshold':.5}
    url = 'wss://api.sarvam.ai/speech-to-text-realtime/ws?' + urlencode(parameters)
    try:
        with connect(url, additional_headers={'api-subscription-key':key},
                     open_timeout=8, close_timeout=2, max_size=1024*1024,
                     ping_interval=15, ping_timeout=15) as socket:
            messages = queue.Queue(maxsize=256)
            receiver_stop = threading.Event()
            failed = threading.Event()

            def receive():
                try:
                    while not stop.is_set() and not receiver_stop.is_set():
                        try: message = socket.recv(timeout=.2)
                        except TimeoutError: continue
                        messages.put_nowait(json.loads(message))
                except (WebSocketException, OSError, ValueError, queue.Full):
                    failed.set()

            receiver = threading.Thread(target=receive, daemon=True)
            receiver.start()
            try:
                state = TranscriptTurn()
                # WAV audit buffer holds up to five minutes; transcript is not
                # cut into a reply at that boundary. Rolling audio is labelled.
                audio = deque(maxlen=4688)
                prefix = deque(maxlen=10)
                collecting = False
                blocked_until = 0.0
                last_preview = ''
                last_status = 0.0
                with sr.Microphone(sample_rate=16000, chunk_size=1024) as source:
                    while not stop.is_set():
                        data = source.stream.read(1024)
                        now = time.monotonic()
                        if failed.is_set(): raise RuntimeError('Realtime transcription connection closed')
                        if playing(): blocked_until = now + .5
                        blocked = now < blocked_until
                        if now-last_status >= 1:
                            on_status({'transport':'sarvam_realtime', 'microphone_frame_received':True,
                                'speaker_gate':blocked, 'pending_final_segments':len(state.segments)})
                            last_status = now
                        if blocked:
                            state, collecting, last_preview = TranscriptTurn(), False, ''
                            audio.clear()
                            prefix.clear()
                            on_speaking(False)
                        else:
                            prefix.append(data)
                            if collecting: audio.append(data)
                        socket.send(json.dumps({'event':'audio_input',
                            'audio':base64.b64encode(bytes(len(data)) if blocked else data).decode('ascii')}))
                        for _ in range(256):
                            try: event = messages.get_nowait()
                            except queue.Empty: break
                            if event.get('event') == 'error':
                                raise RuntimeError('Realtime transcription provider error')
                            if blocked: continue
                            if event.get('event') in {'vad.speech_start','transcript.partial','transcript.final'}:
                                if not collecting:
                                    audio.extend(prefix)
                                    collecting = True
                            state.accept(event, now)
                            if state.preview and state.preview != last_preview:
                                last_preview = state.preview
                                on_partial(state.preview)
                            on_speaking(state.speaking or bool(state.segments))
                        if state.ready(now):
                            turn = state.recognized()
                            captured = sr.AudioData(b''.join(audio), 16000, 2)
                            state, collecting, last_preview = TranscriptTurn(), False, ''
                            audio.clear()
                            on_speaking(False)
                            yield captured, turn
                        elif not state.speaking and not state.segments:
                            collecting = False
                            audio.clear()
            finally:
                receiver_stop.set()
                socket.close()
                receiver.join(timeout=2)
    except (WebSocketException, OSError, TimeoutError) as error:
        # Never surface headers, keys or raw provider bodies.
        raise RuntimeError('Realtime transcription unavailable; restart Voice Chat') from error
