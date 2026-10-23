"""Explicit English one-time reminder requests; no model-invented actions."""
import re

WORDS = {word: index for index, word in enumerate(('zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty'))}
WORDS.update({'thirty':30, 'forty':40, 'forty-five':45, 'sixty':60})

def parse_reminder(text):
    match = re.fullmatch(r"(?:please\s+)?remind me to (.{1,160}?) in (?:the next )?(\d+(?:\.\d+)?|[a-z-]+) (seconds?|minutes?|hours?)[.!?]?", text.strip(), re.I)
    if not match:
        return None
    title, quantity, unit = match.groups()
    amount = WORDS.get(quantity.lower())
    if amount is None:
        try:
            amount = float(quantity)
        except ValueError:
            return None
    seconds = amount * (3600 if unit.lower().startswith('hour') else 60 if unit.lower().startswith('minute') else 1)
    return (title.strip(), seconds) if 1 <= seconds <= 86400 else None
