"""Safe provider diagnostics without storing prompts, keys or raw error bodies."""
from datetime import datetime, timezone
import json
import re

from .paths import RUNTIME_DIR


class ReplyProviderError(RuntimeError):
    pass


def groq_error(response, model):
    try:
        error = response.json().get('error', {})
    except (ValueError, AttributeError):
        error = {}
    message = str(error.get('message', '')).lower()
    status = response.status_code
    category = 'provider_error'
    detail = f'Groq reply failed (HTTP {status}).'
    if status == 429:
        category = 'rate_limit'
        unit = 'token' if error.get('type') == 'tokens' else 'request'
        window = 'per-minute' if 'per minute' in message else 'per-day' if 'per day' in message else ''
        detail = f'Groq {window} {unit} limit reached.'.replace('  ', ' ')
    elif status == 401:
        category, detail = 'authentication', 'Groq rejected the API key.'
    elif status == 403:
        category, detail = 'access', 'Groq denied access to this model or project.'
    elif status == 413:
        category, detail = 'request_size', 'The conversation is too large for Groq.'
    elif status >= 500:
        category, detail = 'unavailable', 'Groq is temporarily unavailable.'
    retry = response.headers.get('retry-after', '')
    if re.fullmatch(r'\d+(?:\.\d+)?', retry):
        detail += f' Try again in {retry} seconds.'
    record = {'time_utc': datetime.now(timezone.utc).isoformat(), 'provider': 'groq',
              'model': model, 'status': status, 'category': category,
              'retry_after_seconds': float(retry) if re.fullmatch(r'\d+(?:\.\d+)?', retry) else None}
    for name in ('x-ratelimit-limit-tokens', 'x-ratelimit-remaining-tokens',
                 'x-ratelimit-limit-requests', 'x-ratelimit-remaining-requests'):
        value = response.headers.get(name, '')
        if value.isdigit():
            record[name] = int(value)
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        (RUNTIME_DIR / 'reply-provider-error.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    except OSError:
        pass  # A diagnostic write must not hide the actionable provider error.
    return ReplyProviderError(detail)
