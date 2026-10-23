"""Stable speech text for the familiar greeting; UI/profile remain Manglish."""
import hashlib
import io
import json
import re
import wave
from pathlib import Path


MANGGLISH_GREETING = 'Enthaa mone, sukhamaano? Innu divasam engane undaayirunnu?'
NATIVE_GREETING = ('\u0d0e\u0d28\u0d4d\u0d24\u0d3e \u0d2e\u0d4b\u0d28\u0d47, '
    '\u0d38\u0d41\u0d16\u0d2e\u0d3e\u0d23\u0d4b? '
    '\u0d07\u0d28\u0d4d\u0d28\u0d4d \u0d26\u0d3f\u0d35\u0d38\u0d02 '
    '\u0d0e\u0d19\u0d4d\u0d19\u0d28\u0d46\u0d2f\u0d41\u0d23\u0d4d\u0d1f\u0d3e\u0d2f\u0d3f\u0d30\u0d41\u0d28\u0d4d\u0d28\u0d41?')


def canonical_greeting(text: str, language: str) -> str | None:
    def normalized(value):
        return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()
    if language == 'ml-IN' and (text == NATIVE_GREETING or
                               normalized(text) == normalized(MANGGLISH_GREETING)):
        return NATIVE_GREETING
    return None


def cached_greeting_audio(conversation, text, turn, whole_text, cache_root: Path) -> bytes:
    """Cache only the fixed, non-personal greeting; settings invalidate the key."""
    voice_id, _ = conversation.voice_for(turn, whole_text)
    identity = {'version': 1, 'text': text, 'language': turn.language, 'voice': voice_id,
                'delivery': conversation.profile.data.get('speech_delivery', {}),
                'pronunciations': conversation.profile.data.get('pronunciations', {})}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    cache_root.mkdir(parents=True, exist_ok=True)
    path = cache_root/(digest+'.wav')
    if path.exists():
        try:
            audio = path.read_bytes()
            with wave.open(io.BytesIO(audio), 'rb') as wav:
                if wav.getnframes() > 0:
                    return audio
        except (OSError, wave.Error, EOFError):
            pass  # Corrupt/incomplete cache is regenerated; provider errors propagate.
    audio = conversation.synthesize(text, turn, whole_text)
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        if wav.getnframes() <= 0:
            raise ValueError('Greeting audio is empty')
    from uuid import uuid4
    temporary = cache_root/(digest+'-'+uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(audio)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return audio
