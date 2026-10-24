"""Sarvam speech recognition, language-aware replies and selected cloned voices.

No microphone access or conversation logging occurs in this module.
"""
import base64
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path
import re
import time
import wave

import httpx

from .paths import PROJECT_ROOT
from .character_profile import CharacterProfile
from .pronunciation import spoken_text
from .reply_errors import ReplyProviderError, groq_error
from .reply_fallback import ReplyFallback
from .address_preferences import address_segments
from .model_router import Route, choose_tier, log_route

SUPPORTED = {'ml-IN': 'Malayalam', 'en-IN': 'English', 'hi-IN': 'Hindi'}
REPLY_PROVIDERS = {'auto', 'groq', 'openai', 'sarvam'}
RETRY_COOLDOWN_SECONDS = 30
BROKEN_COOLDOWN_SECONDS = 600


class ReplyLanguageError(ValueError):
    """A recoverable language mismatch, rather than a stopped voice session."""


class IncompleteReply(ValueError):
    """The model answered but not usably; a stronger tier may succeed."""


class _ProviderFailure(Exception):
    def __init__(self, error: Exception, cooldown: float):
        super().__init__(str(error))
        self.error = error
        self.cooldown = cooldown


def matches_language(text: str, language: str) -> bool:
    malayalam = bool(re.search(r'[\u0d00-\u0d7f]', text))
    hindi = bool(re.search(r'[\u0900-\u097f]', text))
    return malayalam if language == 'ml-IN' else hindi if language == 'hi-IN' else not (malayalam or hindi)


def localized_address(text: str, language: str, profile: CharacterProfile) -> str:
    """Keep a model's carried-over family address in the current language."""
    defaults = {'ml-IN': 'mone', 'hi-IN': 'beta', 'en-IN': 'son'}
    selected = profile.data.get('address_by_language', {}).get(language, defaults[language])
    explicit=getattr(profile,'address_preference',None)
    if explicit: selected=explicit['term']
    spoken = {'mone': '\u0d2e\u0d4b\u0d28\u0d47', 'beta': '\u092c\u0947\u091f\u093e'}
    replacement = spoken.get(selected, selected) if language != 'en-IN' else selected
    return re.sub(r'(?<!\w)(?:mone|beta|\u0d2e\u0d4b\u0d28\u0d47|\u092c\u0947\u091f\u093e)(?!\w)',
                  lambda _: replacement, text, flags=re.IGNORECASE)


def mixed_malayalam(text: str) -> bool:
    return bool(re.search(r'[\u0d00-\u0d7f]', text) and re.search(r'[A-Za-z]{2,}', text))


def speech_chunks(text: str, limit: int = 220) -> list[str]:
    """Prefer sentence boundaries; never drop text or split a long word silently."""
    result = []
    pending = ''
    for sentence in re.split(r'(?<=[.!?।])\s+', text.strip()):
        if not sentence:
            continue
        if len(pending) + len(sentence) + 1 <= limit:
            pending = (pending + ' ' + sentence).strip()
            continue
        if pending:
            result.append(pending)
            pending = ''
        for word in sentence.split():
            if len(word) > limit:
                raise ValueError('Reply contains an overlong token; cannot synthesize safely')
            if len(pending) + len(word) + 1 > limit:
                result.append(pending)
                pending = word
            else:
                pending = (pending + ' ' + word).strip()
    if pending:
        result.append(pending)
    return result


def compact_reply(text: str, max_words: int = 45, max_sentences: int = 2) -> str:
    """Keep spoken replies short even when a provider ignores the prompt."""
    sentences = [part.strip() for part in re.split(r'(?<=[.!?।॥])\s+', text.strip()) if part.strip()]
    if len(sentences) > max_sentences:
        text = ' '.join(sentences[:max_sentences])
    words = text.split()
    if len(words) > max_words:
        text = ' '.join(words[:max_words]).rstrip(' ,;:-') + '.'
    return text


@dataclass
class RecognizedTurn:
    text: str
    language: str
    confidence: float | None
    mixed: bool


class SarvamConversation:
    def __init__(self, api_key: str, config_path: Path | None = None,
                 transport: httpx.BaseTransport | None = None,
                 openai_api_key: str | None = None,
                 groq_api_key: str | None = None,
                 reply_provider: str | None = None,
                 request_timeout: float = 120, connect_timeout: float = 15):
        config_path = config_path or PROJECT_ROOT/'config/voice.json'
        self.config = json.loads(config_path.read_text(encoding='utf-8'))
        self.profile = CharacterProfile.load()
        self.client = httpx.Client(base_url='https://api.sarvam.ai',
            headers={'api-subscription-key': api_key}, transport=transport,
            timeout=httpx.Timeout(request_timeout, connect=connect_timeout), follow_redirects=False)
        self.history: list[dict] = []
        self.last_language = 'ml-IN'
        openai_key = os.environ.get('OPENAI_API_KEY', '').strip() if openai_api_key is None else openai_api_key.strip()
        # Separate clients ensure one provider's credentials never reach another.
        self.openai_client = httpx.Client(base_url='https://api.openai.com',
            headers={'Authorization': 'Bearer ' + openai_key}, transport=transport,
            timeout=httpx.Timeout(min(request_timeout, 90), connect=connect_timeout), follow_redirects=False) if openai_key else None
        self.openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini').strip() or 'gpt-4.1-mini'
        self.openai_deep_model = os.environ.get('OPENAI_DEEP_MODEL', 'gpt-4.1').strip() or 'gpt-4.1'
        groq_key = os.environ.get('GROQ_API_KEY', '').strip() if groq_api_key is None else groq_api_key.strip()
        self.groq_client = httpx.Client(base_url='https://api.groq.com/openai/v1',
            headers={'Authorization': 'Bearer ' + groq_key}, transport=transport,
            timeout=httpx.Timeout(min(request_timeout, 90), connect=connect_timeout), follow_redirects=False) if groq_key else None
        self.groq_model = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-20b').strip() or 'openai/gpt-oss-20b'
        self.reply_fallback = ReplyFallback(transport, sarvam_key=api_key,
            sarvam_model=self.config['chat_model'])
        self.reply_provider = reply_provider or os.environ.get('REPLY_PROVIDER', '').strip() or (
            'auto' if openai_key else 'groq' if groq_key else 'sarvam')
        if self.reply_provider not in REPLY_PROVIDERS:
            self.close()
            raise ValueError('REPLY_PROVIDER must be auto, groq, openai or sarvam')
        if ((self.reply_provider == 'groq' and not groq_key) or (self.reply_provider == 'openai' and not openai_key)
                or (self.reply_provider == 'auto' and not (openai_key or groq_key))):
            self.close()
            raise ValueError('The selected reply provider API key is missing')
        self._cooldowns: dict[tuple[str, str], float] = {}
        self.last_route: dict | None = None

    def close(self) -> None:
        if getattr(self, 'reply_fallback', None):
            self.reply_fallback.close()
        self.client.close()
        if self.openai_client:
            self.openai_client.close()
        if self.groq_client:
            self.groq_client.close()

    def _payload(self, response: httpx.Response) -> dict:
        if not response.is_success:
            # Avoid returning raw provider bodies or secrets to a UI/log.
            raise RuntimeError(f'Sarvam request failed (HTTP {response.status_code}). Check access, balance or network.')
        return response.json()

    def recognize(self, wav: bytes) -> RecognizedTurn | None:
        data = self._payload(self.client.post('/speech-to-text', files=[
            ('file', ('utterance.wav', wav, 'audio/wav')),
            ('model', (None, self.config['stt_model'])),
            ('language_code', (None, 'unknown')),
            ('mode', (None, 'codemix')),
        ]))
        text = (data.get('transcript') or '').strip()
        if not text:
            return None
        language = data.get('language_code')
        # Script evidence helps when short or mixed utterances are ambiguous.
        if re.search(r'[\u0d00-\u0d7f]', text):
            language = 'ml-IN'
        elif re.search(r'[\u0900-\u097f]', text):
            language = 'hi-IN'
        elif language in (None, 'unknown'):
            language = self.last_language
        if language not in SUPPORTED:
            raise ValueError('This companion currently supports Malayalam, English and Hindi. Please use one of these languages.')
        self.last_language = language
        return RecognizedTurn(text, language, data.get('language_probability'), mixed_malayalam(text))

    def _instruction(self, turn: RecognizedTurn, compact: bool, repair: bool) -> str:
        instruction = (
            (self.profile.reply_instructions(turn.language) if compact
             else self.profile.instructions(turn.language)) +
            f'Reply in {SUPPORTED[turn.language]} to this turn. '
            + ('The user is mixing Malayalam and English; mirror that naturally, keeping English terms in Latin script. '
               if turn.mixed else 'Keep your reply in this language; do not add an English translation. ')
            + f'Give a direct, natural answer in a conversational length, no more than {self.profile.reply_word_limit()} words. '
            'Do not add hesitation sounds, filler words, stutters or repeated phrases. '
            'Follow the configured companion role and tone, using everyday conversational delivery rather than narration or a service script. '
            'Match the emotional context: gentle reassurance for worry, light warmth for everyday chat, '
            'quiet enthusiasm for good news. Do not force cheerfulness when the user is upset. '
            'Use ordinary conversational phrasing and light punctuation, without ellipses, long comma chains or theatrical pauses. '
            'Do not use emoji, markdown, stage directions or sound-effect descriptions. '
            'Respond to what actually happened; celebrate good news without treating it as worry. '
            'Do not end with generic offers of help. '
            'Do not copy fillers from the user. Ask a brief clarification if needed.'
        )
        instruction += (
            f' The current response language is {SUPPORTED[turn.language]}. This overrides languages in old memories. '
            'Do not copy the language of previous assistant messages. '
            + ('Use English Latin-script words only.' if turn.language == 'en-IN' else 'Use the native script for speech.')
        )
        if repair:
            instruction += ' The previous attempt used the wrong language. Rewrite the answer in ONLY the requested language.'
        preferred=getattr(self.profile,'address_preference',None)
        if preferred:
            instruction+=' Explicit user preference overrides translated pet names: preserve the exact address '+preferred['term']+'. Do not translate it into son or beta. Use it sparingly. Keep the rest of the response in the requested language.'
        return instruction

    def _chain(self, tier: str) -> list[tuple[str, str]]:
        if self.reply_provider == 'groq':
            return [('groq', self.groq_model)]
        if self.reply_provider == 'openai':
            return [('openai', self.openai_model)]
        if self.reply_provider == 'sarvam':
            return [('sarvam', self.config['chat_model'])]
        openai = ([self.openai_deep_model] if tier == 'deep' else []) + [self.openai_model]
        chain = [('openai', model) for model in dict.fromkeys(openai)] if self.openai_client else []
        return chain + ([('groq', self.groq_model)] if self.groq_client else [])

    def reply(self, turn: RecognizedTurn, _repair: bool = False) -> str:
        if not _repair:
            self._turn_tool_results = {}
        route = choose_tier(turn.text, turn.language) if self.reply_provider == 'auto' else Route('fixed', 'reply_provider')
        # A language repair is a failed attempt, so it moves up to the deep tier.
        escalated = _repair and route.tier == 'fast'
        tiers = ['deep'] if escalated else [route.tier] + (['deep'] if route.tier == 'fast' else [])
        for index, tier in enumerate(tiers):
            try:
                text, provider, model = self._generate(turn, tier, _repair)
                break
            except IncompleteReply:
                if index == len(tiers) - 1:
                    raise
                escalated = True
        if not text or len(text) > 900:
            raise ValueError('Reply was empty or too long for a short spoken turn.')
        text = localized_address(text, turn.language, self.profile)
        text = compact_reply(text, max_words=self.profile.reply_word_limit(),
                             max_sentences=self.profile.reply_sentence_limit())
        if not matches_language(text, turn.language):
            if not _repair:
                return SarvamConversation.reply(self, turn, _repair=True)
            raise ReplyLanguageError('I could not switch languages for that reply. Please say it again; I am still listening.')
        self.last_route = {'tier': tier, 'reason': route.reason, 'provider': provider, 'model': model,
                           'escalated': escalated}
        log_route(self.last_route)
        self.history.extend([{'role': 'user', 'content': turn.text}, {'role': 'assistant', 'content': text}])
        self.history = self.history[-8:]
        return text

    def _generate(self, turn: RecognizedTurn, tier: str, repair: bool) -> tuple[str, str, str]:
        chain = self._chain(tier)
        now = time.monotonic()
        # Cooldowns only skip known-failing models; if all are cooling, try them anyway.
        ready = [link for link in chain if self._cooldowns.get(link, 0) <= now] or chain
        for index, (provider, model) in enumerate(ready):
            try:
                return self._complete(turn, provider, model, repair), provider, model
            except _ProviderFailure as failure:
                self._cooldowns[(provider, model)] = time.monotonic() + failure.cooldown
                if index == len(ready) - 1:
                    raise failure.error from failure
        raise ReplyProviderError('No reply model is configured.')

    def _complete(self, turn: RecognizedTurn, provider: str, model: str, repair: bool) -> str:
        instruction = self._instruction(turn, provider == 'groq', repair)
        # Keep factual user/context evidence; do not prime the model with replies
        # in a language the user has just switched away from.
        history = [m for m in self.history[-8:] if m['role'] != 'assistant'
                   or matches_language(m['content'], turn.language)]
        messages = [{'role': 'system', 'content': instruction}] + history + [
            {'role': 'user', 'content': turn.text}]
        if provider == 'sarvam':
            data = self._payload(self.client.post('/v1/chat/completions', json={
                'model': model, 'messages': messages,
                'max_tokens': 350, 'temperature': .3, 'stream': False, 'reasoning_effort': None,
            }))
            choices = data.get('choices') or []
            if not choices or choices[0].get('finish_reason') == 'length':
                raise ValueError('Reply was incomplete. Please try a shorter question.')
            return (choices[0].get('message', {}).get('content') or '').strip()
        payload = {'model': model, 'messages': messages, 'stream': False}
        if provider == 'groq':
            payload['max_completion_tokens'] = 768
            if model.startswith('openai/gpt-oss'):
                payload['reasoning_effort'] = 'low'
        else:
            payload['max_completion_tokens'] = 500
            payload['store'] = False
        tools = getattr(self,'agent_tools',None)
        plain_greeting = re.fullmatch(r'\s*(?:hi|hello|hey|good morning|good evening|good night|how are you)[!?.\s]*',turn.text,re.I)
        if tools and not plain_greeting:
            payload['tools'] = tools.schemas
            payload['parallel_tool_calls'] = False
        choices = []
        for attempt in range(4):
            choices = self._post(provider, model, payload).json().get('choices') or []
            message = choices[0].get('message', {}) if choices else {}
            calls = message.get('tool_calls') or []
            if not calls or not tools:
                break
            if attempt == 3 or len(calls)>4:
                raise IncompleteReply('Tool limit reached for this turn. Please make a shorter request.')
            messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls})
            for call in calls:
                function = call.get('function',{})
                name = function.get('name','')
                try:
                    arguments=json.loads(function.get('arguments','{}'))
                except (ValueError,TypeError):
                    arguments=None
                key = name+json.dumps(arguments,sort_keys=True)
                if key not in self._turn_tool_results:
                    self._turn_tool_results[key] = tools.execute(name,arguments,turn.text)
                messages.append({'role':'tool','tool_call_id':call['id'],
                                 'content':json.dumps(self._turn_tool_results[key],ensure_ascii=False)})
        if not choices or choices[0].get('finish_reason') != 'stop':
            raise IncompleteReply('Reply was incomplete. Please try a shorter question.')
        return (choices[0].get('message', {}).get('content') or '').strip()

    def _post(self, provider: str, model: str, payload: dict) -> httpx.Response:
        name = 'Groq' if provider == 'groq' else 'OpenAI'
        try:
            if provider == 'groq':
                response = self.reply_fallback.post(self.groq_client, payload)
            else:
                response = self.openai_client.post('/v1/chat/completions', json=payload)
                ReplyFallback._usage(response, payload, 'openai')
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise _ProviderFailure(ReplyProviderError(f'{name} could not be reached. Check the network connection.'),
                                   RETRY_COOLDOWN_SECONDS) from error
        if response.is_success:
            return response
        if provider == 'groq':
            error = groq_error(response, model)
        else:
            error = ReplyProviderError(f'OpenAI reply failed (HTTP {response.status_code}). '
                                       'Check API key, model access or API credit balance.')
        if response.status_code in {401, 403, 404}:
            cooldown = BROKEN_COOLDOWN_SECONDS
        else:
            try:
                cooldown = min(BROKEN_COOLDOWN_SECONDS, max(1.0, float(response.headers.get('retry-after', ''))))
            except ValueError:
                cooldown = RETRY_COOLDOWN_SECONDS
        raise _ProviderFailure(error, cooldown)

    def voice_for(self, turn: RecognizedTurn, reply: str = '') -> tuple[str, int]:
        route = 'malayalam_mixed' if turn.language == 'ml-IN' and (turn.mixed or mixed_malayalam(reply)) else turn.language
        selected = self.config['voices'][route]
        return selected['voice_id'], selected['reference_clip']

    def synthesize(self, text: str, turn: RecognizedTurn, whole_reply: str = '') -> bytes:
        segments=address_segments(text,turn.language,getattr(self.profile,'address_preference',None))
        audios=[self._synthesize_segment(segment,turn,whole_reply or text,language) for segment,language in segments]
        if len(audios)==1: return audios[0]
        output=io.BytesIO()
        with wave.open(output,'wb') as writer:
            expected=None
            for data in audios:
                with wave.open(io.BytesIO(data),'rb') as reader:
                    shape=(reader.getnchannels(),reader.getsampwidth(),reader.getframerate(),reader.getcomptype())
                    if expected is None: expected=shape; writer.setparams(reader.getparams())
                    elif shape!=expected: raise ValueError('Speech segment formats did not match')
                    writer.writeframes(reader.readframes(reader.getnframes()))
        return output.getvalue()

    def _synthesize_segment(self,text,turn,whole_reply,speech_language):
        voice_id, _ = self.voice_for(turn, whole_reply or text)
        text = spoken_text(text, speech_language, self.profile.data.get('pronunciations', {}))
        pace = float(self.profile.data.get('speech_delivery', {}).get('pace', 1.18))
        if not .5 <= pace <= 2:
            raise ValueError('Amma speech pace must be between 0.5 and 2.0')
        data = self._payload(self.client.post('/voices/clone', files=[
            ('voice_id', (None, voice_id)), ('text', (None, text)),
            ('language_code', (None, speech_language)), ('output_audio_codec', (None, 'wav')),
            ('speech_sample_rate', (None, '24000')),
            ('enable_qc', (None, str(bool(self.profile.data.get('speech_delivery', {}).get('enable_qc', False))).lower())),
            ('pace', (None, str(pace))), ('enable_vad', (None, 'true')),
            ('enable_text_normalization', (None, 'true')),
        ]))
        audio = base64.b64decode(data.get('audio_b64') or data.get('audio') or '', validate=True)
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            if wav.getnframes() <= 0:
                raise ValueError('Sarvam returned empty speech')
        return audio

    def stream_speech(self, text: str, turn: RecognizedTurn):
        """Headerless 24 kHz PCM from the cloned-voice streaming endpoint."""
        voice_id, _ = self.voice_for(turn,text)
        text = spoken_text(text,turn.language,self.profile.data.get('pronunciations',{}))
        pace=float(self.profile.data.get('speech_delivery',{}).get('pace',1.18))
        if not .5 <= pace <= 2:
            raise ValueError('Speech pace must be between 0.5 and 2.0')
        with self.client.stream('POST','/voices/clone/stream',files=[
            ('voice_id',(None,voice_id)),('text',(None,text)),('language_code',(None,turn.language)),
            ('output_audio_codec',(None,'linear16')),('speech_sample_rate',(None,'24000')),
            ('pace',(None,str(pace))),('enable_text_normalization',(None,'true'))]) as response:
            if not response.is_success:
                raise RuntimeError(f'Sarvam streaming speech failed (HTTP {response.status_code}).')
            for chunk in response.iter_bytes(4800):
                if chunk:
                    yield chunk
