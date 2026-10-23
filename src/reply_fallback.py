"""Optional local OmniRoute fallback; upstream accounts are configured in its UI."""
import os
import time
import threading
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from .paths import RUNTIME_DIR

_COOLDOWNS = {}
_COOLDOWN_LOCK = threading.Lock()


class ReplyFallback:
    def __init__(self, transport=None, *, sarvam_key=None, sarvam_model=None):
        self.model = os.environ.get('OMNIROUTE_MODEL', '').strip()
        key = os.environ.get('OMNIROUTE_API_KEY', '').strip()
        base = os.environ.get('OMNIROUTE_BASE_URL', 'http://127.0.0.1:20128/v1').rstrip('/')
        parsed = urlsplit(base)
        if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.scheme != 'http' or parsed.username or parsed.password:
            raise ValueError('OmniRoute fallback must use a local HTTP endpoint')
        self.client = httpx.Client(base_url=base, headers={'Authorization': 'Bearer ' + key},
            transport=transport, timeout=httpx.Timeout(25, connect=3), follow_redirects=False) if key and self.model else None
        self.cooldown_until = 0.0
        self.sarvam_model = sarvam_model or 'sarvam-105b-conversations'
        sarvam_key = sarvam_key or os.environ.get('SARVAM_API_KEY','').strip()
        self.sarvam_client = httpx.Client(base_url='https://api.sarvam.ai',
            headers={'api-subscription-key':sarvam_key},transport=transport,
            timeout=httpx.Timeout(35,connect=5),follow_redirects=False
        ) if os.environ.get('SARVAM_REPLY_FALLBACK','0')=='1' and sarvam_key else None

    def post(self, primary, payload):
        signature = hashlib.sha256((str(getattr(primary,'base_url',''))+str(primary.headers.get('Authorization',''))+
            str(payload.get('model',''))).encode()).hexdigest()
        with _COOLDOWN_LOCK:
            cooldown = _COOLDOWNS.get(signature,0)
        if (self.client or self.sarvam_client) and time.monotonic() < max(self.cooldown_until,cooldown):
            return self._fallback(payload)
        try:
            response = primary.post('/chat/completions', json=payload)
        except (httpx.TimeoutException, httpx.NetworkError):
            if not (self.client or self.sarvam_client):
                raise
            return self._fallback(payload)
        self._usage(response,payload,'groq')
        if (self.client or self.sarvam_client) and response.status_code in {408, 429, 500, 502, 503, 504}:
            try:
                delay = float(response.headers.get('retry-after', '15'))
            except ValueError:
                delay = 15
            if 'retry-after' not in response.headers:
                try:
                    hint=str(response.json().get('error',{}).get('message',''))
                    match=re.search(r'try again in (\d+(?:\.\d+)?)(ms|s|m|h)',hint,re.I)
                    if match: delay=float(match[1])*{'ms':.001,'s':1,'m':60,'h':3600}[match[2].lower()]
                except (ValueError,AttributeError,TypeError):
                    pass
            self.cooldown_until = time.monotonic() + min(3600, max(1, delay))
            with _COOLDOWN_LOCK:
                expired=[key for key,value in _COOLDOWNS.items() if value<time.monotonic()]
                for key in expired: _COOLDOWNS.pop(key,None)
                if len(_COOLDOWNS)>64: _COOLDOWNS.clear()
                _COOLDOWNS[signature] = self.cooldown_until
            return self._fallback(payload)
        return response

    def _fallback(self, payload):
        if self.client:
            try:
                return self._omniroute(payload)
            except (httpx.TimeoutException,httpx.NetworkError,RuntimeError):
                if not self.sarvam_client: raise
        if self.sarvam_client:
            request={**payload,'model':self.sarvam_model,'max_tokens':350,'reasoning_effort':None}
            request.pop('max_completion_tokens',None)
            request.pop('parallel_tool_calls',None)
            response=self.sarvam_client.post('/v1/chat/completions',json=request)
            self._usage(response,request,'sarvam_fallback')
            if not response.is_success:
                from .reply_errors import ReplyProviderError
                raise ReplyProviderError(f'Sarvam reply fallback failed (HTTP {response.status_code}). Check its quota or connection.')
            return response
        raise RuntimeError('No independent reply fallback is configured')

    def _omniroute(self,payload):
        request = {**payload, 'model': self.model}
        request.pop('reasoning_effort', None)
        response = self.client.post('/chat/completions', json=request)
        if not response.is_success:
            from .reply_errors import ReplyProviderError
            raise ReplyProviderError(f'OmniRoute fallback failed (HTTP {response.status_code}). Check its connected provider and model.')
        return response

    @staticmethod
    def _usage(response,payload,provider):
        try:
            data=response.json() if response.is_success else {}
            usage=data.get('usage') or {}
            record={'time_utc':datetime.now(timezone.utc).isoformat(),'provider':provider,
                'model':payload.get('model'),'status':response.status_code,
                'message_count':len(payload.get('messages',[])),'tool_count':len(payload.get('tools',[])),
                'request_characters':len(json.dumps(payload,ensure_ascii=False)),
                'usage':{k:usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens') if isinstance(usage.get(k),int)},
                'cached_tokens':(usage.get('prompt_tokens_details') or {}).get('cached_tokens')}
            for name in ('retry-after','x-ratelimit-limit-tokens','x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens'):
                value=response.headers.get(name,'')
                if value and len(value)<40 and all(c.isalnum() or c in '. -' for c in value): record[name]=value
            RUNTIME_DIR.mkdir(parents=True,exist_ok=True)
            with (RUNTIME_DIR/'reply-usage.jsonl').open('a',encoding='utf-8') as file:
                file.write(json.dumps(record)+'\n')
        except (OSError,ValueError,TypeError):
            pass  # Telemetry must not break a valid reply.

    def close(self):
        if self.client:
            self.client.close()
        if self.sarvam_client:
            self.sarvam_client.close()
