"""Picks a reply-model tier from the request text alone, so routing adds no latency."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re

from .paths import RUNTIME_DIR

LONG_REQUEST_WORDS = 30

_ENGLISH_CUES = re.compile(
    r"\b(?:plan|planning|compare|comparison|difference between|pros and cons|explain|why|"
    r"how (?:does|do|did|can|could|to|would|should)|step by step|walk me through|research|"
    r"analy[sz]e|summari[sz]e|strategy|recommend|which (?:one )?is better|should i|"
    r"help me (?:write|decide|understand|prepare)|"
    r"write (?:an?|the|my) (?:email|essay|letter|story|code|program|script|report|cover letter)|"
    r"debug|solve|"
    # Romanized Hindi and Malayalam
    r"kyon|kyun|samjhao|samjhaiye|tulna|yojana|enthukondu|vishadeekari\w*|tharathamyam)\b",
    re.IGNORECASE)

# Indic vowel signs are not word characters, so native-script cues match as substrings.
_NATIVE_CUES = ('क्यों', 'तुलना', 'समझा', 'योजना', 'विस्तार से', 'फायदे और नुकसान',
                'എന്തുകൊണ്ട്', 'വിശദീകരി', 'താരതമ്യ', 'വിശദമായി', 'പ്ലാൻ')


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str


def choose_tier(text: str, language: str = 'en-IN') -> Route:
    value = text.strip()
    if len(value.split()) > LONG_REQUEST_WORDS:
        return Route('deep', 'long_request')
    if value.count('?') >= 2:
        return Route('deep', 'multi_part')
    if _ENGLISH_CUES.search(value) or any(cue in value for cue in _NATIVE_CUES):
        return Route('deep', 'reasoning_keyword')
    return Route('fast', 'default')


def log_route(route: dict) -> None:
    """Record routing outcomes, never conversation text, for tuning the rules later."""
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with (RUNTIME_DIR/'model-routes.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps({'time_utc': datetime.now(timezone.utc).isoformat(), **route}) + '\n')
    except OSError:
        pass  # Telemetry must not break a valid reply.
