"""Native continuous microphone capture with cancellable cloned-voice replies."""
import io
import os
import json
import re
import time
from datetime import datetime, timezone
import threading
import queue
import wave
import winsound

import httpx
import speech_recognition as sr

from .sarvam_conversation import speech_chunks
from .live_conversation import LiveConversation
from .paths import RUNTIME_DIR
from .character_profile import CharacterProfile
from .sarvam_conversation import RecognizedTurn, SarvamConversation, ReplyLanguageError
from .speech_motion import SpeechMotion
from .greeting_speech import canonical_greeting, cached_greeting_audio
from .native_capture import MonitoredStream
from .realtime_input import capture_turns


class SarvamVoiceAgent:
    def __init__(self, api_key: str):
        self._key = api_key
        self._thread = None
        self._stop = threading.Event()
        self._play_lock = threading.Lock()
        self.active = False
        self.on_state_change = None
        self.on_text_partial = None
        self.on_text_final = None
        self.on_transcript = None
        self.on_transcript_partial = None
        self.on_speech_motion = None
        self.profile = CharacterProfile.load()
        self.muted = not bool(self.profile.greetings.get('speak', False))
        self._lifecycle_lock = threading.Lock()
        self.observations = lambda: []
        self.camera_frame = None
        self.camera_request = None
        self.study_check = None
        self._phase = 'idle'
        self._turn_cancel = threading.Event()
        self._work_busy = threading.Event()
        self._reply_thread = None
        self._restart_pending = False
        self._restart_thread = None
        self.voice_interruptions = False  # Enable with headphones; no native AEC yet.
        self._playing = threading.Event()
        self._input_speaking = threading.Event()
        self._epoch = 0
        self._reply_epoch = None
        self.pause_seconds = 2.2
        self.realtime_input = os.environ.get('SETTA_REALTIME_INPUT', '1') == '1'

    def _notify(self, callback, value) -> None:
        if callback:
            callback(value)

    def start(self) -> None:
        with self._lifecycle_lock:
            self._start_locked()

    def _start_locked(self) -> None:
        if self.active:
            return
        previous_threads = tuple(thread for thread in (self._thread, self._reply_thread)
                                 if thread and thread.is_alive())
        if previous_threads:
            if not self._stop.is_set():
                self._notify(self.on_text_final, 'Voice Chat is still starting. Please wait a moment.')
                return
            self._restart_pending = True
            if not (self._restart_thread and self._restart_thread.is_alive()):
                self._restart_thread = threading.Thread(
                    target=self._restart_after_previous_session, daemon=True)
                self._restart_thread.start()
            self._notify(self.on_text_final, 'Restarting Voice Chat after the previous turn finishes.')
            return
        self._stop.clear()
        self._turn_cancel.clear()
        # Selecting Voice Chat is an explicit request for audible conversation.
        # The microphone still stays off until this action.
        self.muted = False
        self.active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _restart_after_previous_session(self) -> None:
        while True:
            previous_threads = tuple(thread for thread in (self._thread, self._reply_thread)
                                     if thread and thread.is_alive()
                                     and thread is not threading.current_thread())
            if not previous_threads:
                break
            for thread in previous_threads:
                thread.join()
        with self._lifecycle_lock:
            if self._restart_thread is threading.current_thread():
                self._restart_thread = None
            if not self._restart_pending:
                return
            self._restart_pending = False
            self._start_locked()

    @property
    def busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def say_greeting(self, text: str, language: str = 'ml-IN') -> bool:
        """Speak one recognized-person greeting, without opening a microphone."""
        with self._lifecycle_lock:
            if self.active or self.busy or self.muted or not text.strip():
                return False
            self._stop.clear()
            self._turn_cancel.clear()
            self._thread = threading.Thread(target=self._greet, args=(text, language), daemon=True)
            self._thread.start()
            return True

    def _greet(self, text: str, language: str) -> None:
        conversation = None
        try:
            self._phase = 'greeting'
            conversation = LiveConversation(self._key, observations=self.observations, camera_frame=self.camera_frame,
                                           camera_request=self.camera_request, study_check=self.study_check,
                                           request_timeout=35, connect_timeout=5)
            fixed = canonical_greeting(text, language)
            script = {'ml-IN': r'[\u0d00-\u0d7f]', 'hi-IN': r'[\u0900-\u097f]'}.get(language)
            if fixed:
                text = fixed
            elif script and not re.search(script, text):
                text = SarvamConversation.reply(conversation, RecognizedTurn(
                    'Say this short greeting to your son in the requested language. '
                    'Keep its meaning; do not answer the greeting or add a preamble: ' + text,
                    language, None, False))
            if self._stop.is_set():
                return
            turn = RecognizedTurn(text, language, None, False)
            conversation.journal_turn = conversation.journal.new_turn()
            conversation.journal.event(conversation.journal_turn, 'greeting_generated', text=text, language=language)
            self._notify(self.on_text_partial, text)
            for chunk in speech_chunks(text):
                if self._stop.is_set() or self.muted:
                    break
                audio = (cached_greeting_audio(conversation, chunk, turn, text, RUNTIME_DIR/'greeting-cache')
                         if fixed else conversation.synthesize(chunk, turn, text))
                if not self._stop.is_set() and not self.muted:
                    self._play(audio)
            if not self._stop.is_set():
                conversation.memory.add_message(conversation.session.session_id, 'assistant', text, language)
                self._notify(self.on_text_final, text)
        except (httpx.HTTPError, RuntimeError, ValueError, OSError, wave.Error, EOFError) as error:
            self._notify(self.on_text_final, 'Amma could not speak the greeting. Please try Voice Chat.')
        finally:
            if conversation:
                conversation.close()
            self._notify(self.on_state_change, 'idle')

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._restart_pending = False
            self.active = False
            self._stop.set()
        self.interrupt()
        self._notify(self.on_speech_motion, None)
        with self._play_lock:
            winsound.PlaySound(None, 0)

    def cancel_pending_restart(self) -> None:
        with self._lifecycle_lock:
            self._restart_pending = False

    def interrupt(self):
        """Stop only this reply; leave the native microphone session running."""
        self._turn_cancel.set()
        self._epoch += 1
        with self._play_lock:
            winsound.PlaySound(None, 0)
        self._notify(self.on_speech_motion, None)

    def _cancelled(self):
        return (self._stop.is_set() or self._turn_cancel.is_set() or
                (self._reply_epoch is not None and self._reply_epoch != self._epoch))

    def _play(self, audio: bytes) -> None:
        if self._cancelled():
            return
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            duration = wav.getnframes()/wav.getframerate()
        motion = SpeechMotion.from_wav(audio)
        # A unique per-chunk file prevents concurrent overwrite; always removed.
        import tempfile
        from pathlib import Path
        audio_root = RUNTIME_DIR/'voice-temp'
        audio_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='turn-', dir=audio_root) as folder:
            path = Path(folder)/'reply.wav'
            path.write_bytes(audio)
            try:
                with self._play_lock:
                    if self._cancelled():
                        return
                    self._playing.set()
                    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                self._notify(self.on_speech_motion, (motion, time.monotonic()))
                self._notify(self.on_state_change, 'talk')
                deadline = time.monotonic()+duration+.15
                while not self._cancelled() and time.monotonic()<deadline:
                    self._turn_cancel.wait(min(.03, max(0, deadline-time.monotonic())))
            finally:
                self._playing.clear()
                self._notify(self.on_speech_motion, None)
                with self._play_lock:
                    winsound.PlaySound(None, 0)
                if not self._stop.is_set():
                    self._notify(self.on_state_change, 'review')

    def _run(self) -> None:
        captured_turns = queue.Queue(maxsize=1)
        conversation = None
        def replies():
            try:
                while not self._stop.is_set():
                    try:
                        captured, capture_id, epoch, recognized = captured_turns.get(timeout=.2)
                    except queue.Empty:
                        continue
                    self._turn_cancel.clear()
                    self._reply_epoch = epoch
                    self._work_busy.set()
                    try:
                        if self._cancelled():
                            conversation.journal.event(capture_id, 'superseded_before_transcription')
                            continue
                        started = time.monotonic()
                        if recognized is None:
                            conversation.pending_capture_id = capture_id
                            turn = conversation.recognize(captured.get_wav_data(convert_rate=16000, convert_width=2))
                        else:
                            turn = recognized
                            conversation.journal_turn = capture_id
                            conversation._recognized_pending = True
                            conversation.last_language = turn.language
                            conversation.journal.event(capture_id, 'transcription', text=turn.text,
                                                       language=turn.language, transport='realtime')
                        if not turn or self._cancelled():
                            continue
                        if recognized is None and len(captured.frame_data)/(captured.sample_rate*captured.sample_width) >= 26.9:
                            conversation.journal.event(conversation.journal_turn, 'capture_limit', seconds=27)
                            self._notify(self.on_text_final, 'Recording limit reached. Please use a shorter turn.')
                            continue
                        self._process_turn(conversation, turn, time.monotonic()-started)
                        if self._cancelled():
                            last = conversation.memory.recent(1, conversation.session.session_id)
                            if last and last[-1]['role'] == 'assistant':
                                conversation.memory.delete_message(last[-1]['id'])
                            conversation.journal.event(conversation.journal_turn, 'native_reply_interrupted')
                        else:
                            conversation.journal.event(conversation.journal_turn, 'native_playback_finished')
                    except (httpx.HTTPError, RuntimeError, ValueError, OSError, wave.Error, EOFError, KeyError, TypeError, AttributeError) as error:
                        conversation.journal.event(capture_id, 'native_turn_error', error_type=type(error).__name__, phase=self._phase)
                        if not self._cancelled():
                            from .reply_errors import ReplyProviderError
                            message = str(error) if isinstance(error, (ReplyProviderError, ReplyLanguageError)) else 'This turn failed. I am still listening; please try again.'
                            self._notify(self.on_text_final, message)
                    finally:
                        self._work_busy.clear()
                        self._reply_epoch = None
                        if not self._stop.is_set() and not self._input_speaking.is_set():
                            self._notify(self.on_state_change, 'voice_listening')
            except Exception as error:
                self._stop.set()
                self._notify(self.on_text_final, 'The reply worker stopped. Restart Voice Chat to recover.')
                RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
                (RUNTIME_DIR/'voice-error.json').write_text(json.dumps({'phase':'reply_worker','error_type':type(error).__name__}), encoding='utf-8')
            finally:
                if conversation:
                    conversation.close()
        try:
            conversation = LiveConversation(self._key, observations=self.observations, camera_frame=self.camera_frame,
                                           camera_request=self.camera_request, study_check=self.study_check,
                                           request_timeout=35, connect_timeout=5)
            self._reply_thread = threading.Thread(target=replies, daemon=True)
            self._reply_thread.start()
            if self.realtime_input:
                self._run_realtime(conversation, captured_turns)
                return
            recognizer = sr.Recognizer()
            recognizer.pause_threshold = self.pause_seconds
            recognizer.non_speaking_duration = .5
            with sr.Microphone(sample_rate=16000) as source:
                recognizer.adjust_for_ambient_noise(source, duration=.3)
                def speech_started():
                    self._input_speaking.set()
                    if self.voice_interruptions and self._work_busy.is_set():
                        self.interrupt()
                    if not self._playing.is_set() or self.voice_interruptions:
                        self._notify(self.on_state_change, 'voice_capturing')
                stream = MonitoredStream(source.stream,
                    lambda: max(450, recognizer.energy_threshold*1.5), speech_started,
                    playback_active=self._playing.is_set)
                source.stream = stream
                def heartbeat():
                    while not self._stop.wait(1):
                        snapshot = {'time_utc':datetime.now(timezone.utc).isoformat(),
                            'active':self.active, 'reply_busy':self._work_busy.is_set(),
                            'playing_audio':self._playing.is_set(), 'speech_detected':self._input_speaking.is_set(),
                            'reply_worker_alive':bool(self._reply_thread and self._reply_thread.is_alive()),
                            'queued_turns':captured_turns.qsize(), 'pause_seconds':self.pause_seconds,
                            'last_audio_frame_age_seconds':round(time.monotonic()-stream.last_frame_at,2) if stream.last_frame_at else None,
                            'peak_rms':round(stream.peak_rms,1), 'phase':self._phase}
                        try:
                            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
                            (RUNTIME_DIR/'native-voice-status.json').write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
                        except OSError:
                            pass  # Best-effort status; the durable conversation journal is separate.
                threading.Thread(target=heartbeat, daemon=True).start()
                self._notify(self.on_state_change, 'voice_listening')
                while not self._stop.is_set():
                    stream.reset()
                    recognizer.pause_threshold = self.pause_seconds
                    try:
                        captured = recognizer.listen(source, timeout=1, phrase_time_limit=27)
                    except sr.WaitTimeoutError:
                        continue
                    self._input_speaking.clear()
                    if self._stop.is_set():
                        break
                    capture_id = conversation.journal.new_turn()
                    conversation.journal.audio(capture_id, captured.get_wav_data(convert_rate=16000, convert_width=2))
                    duration = len(captured.frame_data)/(captured.sample_rate*captured.sample_width)
                    conversation.journal.event(capture_id, 'native_capture', seconds=round(duration,3),
                        pause_seconds=self.pause_seconds, peak_rms=round(stream.peak_rms,1),
                        speaker_overlap=stream.speaker_audio_detected,
                        end_reason='duration_limit' if duration>=26.9 else 'silence')
                    if not self.voice_interruptions and stream.speaker_audio_detected:
                        conversation.journal.event(capture_id, 'speaker_overlap_rejected')
                        self._notify(self.on_text_final, 'Speaker audio overlapped that recording. Please speak again after Amma stops, or use headphones.')
                        continue
                    # A raw recording is not a validated interruption. In
                    # speaker mode, never cancel a reply because of it.
                    if self._work_busy.is_set() and not self.voice_interruptions:
                        conversation.journal.event(capture_id, 'capture_ignored_during_reply')
                        continue
                    try:
                        _, replaced_id, _, _ = captured_turns.get_nowait()
                        conversation.journal.event(replaced_id, 'superseded_in_queue', replacement=capture_id)
                    except queue.Empty:
                        pass
                    captured_turns.put_nowait((captured, capture_id, self._epoch, None))
                    self._notify(self.on_state_change, 'voice_thinking')
                    self._stop.wait(.01)
        except (OSError, AttributeError, ValueError, RuntimeError, httpx.HTTPError, wave.Error, EOFError) as error:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (RUNTIME_DIR/'voice-error.json').write_text(json.dumps({'phase':'native_session','error_type':type(error).__name__}), encoding='utf-8')
            self._notify(self.on_text_final, 'Voice mode stopped. Check the microphone and connection, then start again.')
        finally:
            self._stop.set()
            self.active = False
            self.interrupt()
            if self._reply_thread and self._reply_thread is not threading.current_thread():
                self._reply_thread.join(timeout=2)
            elif conversation:
                conversation.close()
            self._notify(self.on_state_change, 'idle')

    def _run_realtime(self, conversation, captured_turns):
        self._notify(self.on_state_change, 'voice_listening')
        def status(snapshot):
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            snapshot.update(time_utc=datetime.now(timezone.utc).isoformat(), active=self.active,
                reply_busy=self._work_busy.is_set(), playing_audio=self._playing.is_set(),
                reply_worker_alive=bool(self._reply_thread and self._reply_thread.is_alive()),
                queued_turns=captured_turns.qsize(), phase=self._phase)
            try:
                (RUNTIME_DIR/'native-voice-status.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
            except OSError:
                pass  # Best effort heartbeat; journal failures remain visible.
        def speaking(active):
            if active:
                self._input_speaking.set()
            else:
                self._input_speaking.clear()
        for captured, turn in capture_turns(self._key, self._stop, self._playing.is_set,
                lambda text: self._notify(self.on_transcript_partial, text), speaking, status):
            if self._stop.is_set(): break
            capture_id = conversation.journal.new_turn()
            conversation.journal.audio(capture_id, captured.get_wav_data())
            conversation.journal.event(capture_id, 'native_capture', transport='realtime',
                seconds=round(len(captured.frame_data)/32000, 3),
                end_reason='server_final_with_continuation_hold', audio_buffer='rolling_last_five_minutes')
            # Without headphones, let the current reply finish and queue this
            # complete turn behind it. Automatic interruption is opt-in.
            if self.voice_interruptions:
                self.interrupt()
            try:
                _, replaced_id, _, _ = captured_turns.get_nowait()
                conversation.journal.event(replaced_id, 'superseded_in_queue', replacement=capture_id)
            except queue.Empty:
                pass
            captured_turns.put_nowait((captured, capture_id, self._epoch, turn))
            self._notify(self.on_transcript, turn.text)
            self._notify(self.on_state_change, 'voice_thinking')

    def _wait_for_user(self):
        while self._input_speaking.is_set() and not self._cancelled():
            self._stop.wait(.05)

    def _process_turn(self, conversation, turn, recognition_seconds=0.0):
        self._notify(self.on_transcript, turn.text)
        started = time.monotonic()
        self._phase = 'reply'
        if getattr(conversation, 'agent_tools', None):
            conversation.agent_tools.cancelled = self._cancelled
        answer = conversation.reply(turn)
        reply_seconds = time.monotonic()-started
        if self._cancelled():
            return
        first_audio = None
        synthesis_seconds = 0.0
        if self.muted:
            self._notify(self.on_text_partial, answer)
        for chunk in ([] if self.muted else speech_chunks(answer)):
            self._wait_for_user()
            if self._cancelled():
                return
            self._phase = 'synthesis'
            synthesis_started = time.monotonic()
            audio = conversation.synthesize(chunk, turn, answer)
            synthesis_seconds += time.monotonic()-synthesis_started
            if not self._cancelled():
                if first_audio is None:
                    first_audio = recognition_seconds + time.monotonic()-started
                self._phase = 'playback'
                self._notify(self.on_text_partial, chunk)
                self._play(audio)
        if not self._cancelled():
            self._notify(self.on_text_final, answer)
            # Stage timings only. No transcript, audio, screen title or key.
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            (RUNTIME_DIR/'voice-latency.json').write_text(json.dumps({
                'time_utc': datetime.now(timezone.utc).isoformat(),
                'recognition_seconds': round(recognition_seconds, 3),
                'reply_seconds': round(reply_seconds, 3),
                'synthesis_seconds': round(synthesis_seconds, 3),
                'first_audio_after_capture_seconds': round(first_audio, 3) if first_audio is not None else None,
                'scope': 'Last completed turn; excludes user speech and end-of-speech detection.'
            }, indent=2), encoding='utf-8')
