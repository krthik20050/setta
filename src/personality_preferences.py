"""Bounded, deterministic chat corrections for local companion personality settings."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PersonalityCorrection:
    values: dict[str, str]
    persistent: bool
    command_only: bool


_CHOICES = {
    'reply_length': {
        'brief': r'\b(?:be|keep it|make it|reply|answer|keep (?:your )?(?:replies|answers)) (?:more )?(?:brief|briefly|short|shorter|concise|concisely)\b|\b(?:shorter|more concise|short|brief|concise) replies\b|\bexplain .{0,50} briefly\b|संक्षेप में बताओ|जवाब छोटा|छोटा जवाब|ചുരുക്കി പറയൂ|ചുരുക്കത്തിൽ പറയൂ|kurach(?:u)? short(?: aayi)?|short aayi parayu',
        'detailed': r'\b(?:be|keep it|make it|reply|answer) (?:more )?(?:detailed|longer|in more detail|thorough)\b|\bmore detail\b|\bgive (?:me )?longer answers\b|विस्तार से बताओ|जवाब विस्तार से|വിശദമായി പറയൂ|കൂടുതൽ വിശദമായി|kurach(?:u)? detail aayi',
        'balanced': r'\b(?:go back to|return to) (?:your )?(?:usual|normal|balanced) (?:reply length|answers|replies)\b',
    },
    'advice_style': {
        'ask_first': r'\b(?:ask|check) (?:me )?(?:before|first) (?:giving|offering) advice\b|\b(?:no advice|just listen|listen first|advice only when i ask)\b|\bdon.t give me advice unless i ask\b|मेरे पूछने पर ही सलाह|बिना पूछे सलाह मत दो|मैं पूछूँ तभी सलाह|ഞാൻ ചോദിച്ചാൽ മാത്രം ഉപദേശം|ചോദിക്കാതെ ഉപദേശം വേണ്ട|advice njan chodikkumbol mathram',
        'practical': r'\b(?:give|offer) (?:me )?(?:direct|practical) advice\b|\bbe more practical\b|सीधी सलाह दो|व्यावहारिक सलाह|പ്രായോഗികമായി ഉപദേശം|practical advice tharu',
    },
    'humor': {
        'off': r'\b(?:no jokes|don.t joke|stop joking|skip the jokes|without jokes)\b|मज़ाक मत करो|मजाक मत करो|തമാശ വേണ്ട|തമാശ പറയണ്ട|joke venda',
        'rare': r'\b(?:less joking|fewer jokes|less humor|less humour|not so jokey)\b|कम मज़ाक|कम मजाक|കുറച്ച് തമാശ|jokes kurachu',
        'occasional': r'\b(?:more playful|more jokes|joke a little more|be playful)\b|थोड़ा मज़ाक|थोड़ा मजाक|ഒന്ന് തമാശ പറയൂ|kurach joke',
    },
    'follow_up': {
        'only_when_needed': r'\b(?:ask|add) (?:me )?(?:fewer|less|no) follow[- ]?up questions\b|\bdon.t end every reply with a question\b|\bquestions only when needed\b|कम सवाल पूछो|हर जवाब में सवाल मत|കുറച്ച് ചോദ്യങ്ങൾ|എല്ലാ മറുപടിയിലും ചോദ്യം വേണ്ട|chodyangal kurachu',
        'often': r'\b(?:ask|add) more follow[- ]?up questions\b|\bask me questions more often\b|ज़्यादा सवाल पूछो|കൂടുതൽ ചോദ്യങ്ങൾ ചോദിക്കൂ',
    },
}

_DURABLE = re.compile(
    r'\b(?:from now on|going forward|as my default|by default|always|remember that i prefer|'
    r'make (?:this|that) my default|keep doing that)\b', re.I)
_DURABLE_LOCAL = ('अब से', 'आगे से', 'हमेशा', 'डिफ़ॉल्ट', 'डिफाल्ट', 'इसे मेरी पसंद',
                  'ഇനി മുതൽ', 'എപ്പോഴും', 'സ്ഥിരമായി', 'എന്റെ പതിവായി')


def parse_personality_correction(text: str) -> PersonalityCorrection | None:
    """Recognize a single clear style change; unrelated text never writes a preference."""
    if not isinstance(text, str) or len(text) > 1500:
        return None
    matches = []
    for field, choices in _CHOICES.items():
        for value, pattern in choices.items():
            match = re.search(pattern, text, re.I)
            if match:
                matches.append((match.start(), match.end(), field, value))
    fields = {item[2] for item in matches}
    if not matches or len(fields) != len(matches):
        return None
    # A broader preference change needs a clear request; do not infer from discussion.
    clean = text.casefold()
    if len(matches) > 1 and not re.search(r'\b(?:make|keep|change|set|be|please|from now on|going forward)\b', clean):
        return None
    residual = text
    for start, end, _, _ in reversed(matches):
        residual = residual[:start] + ' ' + residual[end:]
    residual = re.sub(r'\b(?:from now on|going forward|as my default|by default|always|remember that i prefer|please|also|and|okay|actually|then|could you|can you|would you|will you|i want you to|i prefer|i like|i want)\b', ' ', residual, flags=re.I)
    for marker in _DURABLE_LOCAL:
        residual = residual.replace(marker, ' ')
    residual = re.sub(r'[\s,;.!?\-]+', '', residual)
    command_only = not residual
    return PersonalityCorrection(
        values={field: value for _, _, field, value in matches},
        persistent=bool(_DURABLE.search(text) or any(marker in text for marker in _DURABLE_LOCAL)),
        command_only=command_only,
    )
