"""Small local routing rules. Model suggestions never authorize actions."""
from dataclasses import dataclass
from datetime import datetime
import re

from .camera_context import asks_about_eyewear
from .desktop_activity import desktop_question


@dataclass(frozen=True)
class Decision:
    route: str
    source: str = 'rules'
    answer: str | None = None


def decide(text, language, facts=(), now=None):
    normalized = re.sub(r'[?!.,]+$', '', text.strip().casefold()).replace('’', "'")
    if language == 'en-IN':
        current = now or datetime.now().astimezone()
        if normalized in {"what time is it", "what's the time", 'tell me the time'}:
            return Decision('local_clock', answer='It is '+current.strftime('%I:%M %p').lstrip('0')+'.')
        if normalized in {"what is today's date", "what's today's date", 'what is the date today'}:
            return Decision('local_clock', answer='Today is '+current.strftime('%A, %d %B %Y')+'.')
        if normalized in {'what is my name', "what's my name", 'do you remember my name'}:
            name = next((row['value'] for row in facts if row['key'] == 'user_name'), None)
            if isinstance(name, str) and 0 < len(name) <= 80 and '\n' not in name:
                return Decision('local_profile', answer='Your name is '+name+'.')
    if asks_about_eyewear(text):
        return Decision('camera_observation')
    if asks_who_is_visible(text, language):
        return Decision('camera_identity')
    if desktop_question(text):
        return Decision('desktop_context')
    return Decision('reply_model')


def asks_for_current_facts(text):
    """Force explicitly time-sensitive factual questions through live web search."""
    value = re.sub(r'\s+', ' ', str(text or '').strip().casefold())
    is_question = bool(re.search(
        r'^(?:(?:and|also)\s+)?(?:who|what|when|where|which|how many|how much|is|are|tell me|can you tell me|look up|search for)\b',
        value))
    is_time_sensitive = bool(re.search(
        r'\b(?:current(?:ly)?|latest|most recent|recent|today|right now|this week|this month|as of now)\b',
        value))
    return is_question and is_time_sensitive


def asks_who_is_visible(text, language):
    """Recognize direct identity/presence questions across supported languages."""
    value=re.sub(r'[?!.,]+$', '', text.strip().casefold()).replace('’', "'")
    patterns={
        'en-IN': r"(?:who am i|who is this|who's this|who is that|who's that|can you see me|do you recognize me|do you know me)",
        'ml-IN': r'(?:njan aara|njaan aara|ithu aara|ithaaranu|enne kaan(?:unnundo|amo)|enne ariyumo|enne thirichariyumo)',
        'hi-IN': r'(?:main kaun hoon|yeh kaun hai|kaun hoon main|kya tum mujhe dekh sakte ho|kya aap mujhe dekh sakte hain|kya tum mujhe pehchante ho)'
    }
    return bool(re.fullmatch(patterns.get(language, r'(?!)'), value))
