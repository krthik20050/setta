import asyncio
import ctypes
import os
import tempfile
import threading
import edge_tts
import speech_recognition as sr
from .chat import create_client, extract_sentences


class VoiceAgent:
    def __init__(self, gemini_api_key, model="gemini-2.0-flash",
                 voice="en-US-JennyNeural"):
        self.client = create_client(gemini_api_key)
        self.model = model
        self.voice = voice
        self.active = False
        self._thread = None
        self._recognizer = sr.Recognizer()
        self._mic = None
        self.on_state_change = None
        self.on_text_partial = None
        self.on_text_final = None

    def start(self):
        self.active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.active = False

    def _run(self):
        asyncio.run(self._session())

    async def _session(self):
        chat = self.client.aio.chats.create(model=self.model)
        self._mic = sr.Microphone()

        while self.active:
            self._notify_state("voice_listening")
            text = await asyncio.to_thread(self._listen)
            if not text or not self.active:
                continue

            self._notify_state("voice_thinking")
            full_response = []
            tts_tasks = []
            buffer = ""

            try:
                async for chunk in await chat.send_message_stream(text):
                    if not chunk.text or not self.active:
                        continue
                    buffer += chunk.text
                    self._notify_text(buffer)
                    sentences, buffer = extract_sentences(buffer)
                    for s in sentences:
                        full_response.append(s)
                        tts_tasks.append(asyncio.create_task(self._speak(s)))
                        if len(tts_tasks) > 2:
                            tts_tasks.pop(0)
            except Exception:
                if not full_response:
                    self._notify_final("Voice mode unavailable — check Gemini API quota at aistudio.google.com")
                    await asyncio.sleep(3)
                    continue

            if buffer.strip():
                full_response.append(buffer.strip())
                tts_tasks.append(asyncio.create_task(self._speak(buffer.strip())))

            if tts_tasks:
                await asyncio.wait(tts_tasks)

            self._notify_final(" ".join(full_response))

    def _notify_state(self, state):
        if self.on_state_change:
            self.on_state_change(state)

    def _notify_text(self, text):
        if self.on_text_partial:
            self.on_text_partial(text)

    def _notify_final(self, text):
        if self.on_text_final:
            self.on_text_final(text)

    def _listen(self):
        if not self.active:
            return ""
        try:
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=10)
            if not self.active:
                return ""
            return self._recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception:
            return ""

    async def _speak(self, text):
        if not text.strip():
            return
        try:
            tts = edge_tts.Communicate(text.strip(), voice=self.voice)
            tmp = os.path.join(tempfile.gettempdir(), "setta_tts.mp3")
            await tts.save(tmp)
            winmm = ctypes.windll.winmm
            p = tmp.replace("/", "\\")
            winmm.mciSendStringW(f'open "{p}" alias s', None, 0, None)
            winmm.mciSendStringW("play s from 0", None, 0, None)
            while True:
                buf = ctypes.create_unicode_buffer(128)
                winmm.mciSendStringW("status s mode", buf, 128, None)
                if buf.value == "stopped":
                    break
                await asyncio.sleep(0.1)
            winmm.mciSendStringW("close s", None, 0, None)
        except Exception:
            pass
