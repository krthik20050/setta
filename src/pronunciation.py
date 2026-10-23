"""Small language-scoped speech-only word replacements for approved corrections."""
import re


def spoken_text(text: str, language: str, rules: dict) -> str:
    mappings = rules.get(language, {})
    if not mappings:
        return text
    if not isinstance(mappings, dict) or any(not isinstance(k,str) or not k or
            not isinstance(v,str) or not v.strip() for k,v in mappings.items()):
        raise ValueError('Pronunciations must map nonempty words to nonempty spoken forms')
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(key) for key in sorted(mappings,key=len,reverse=True)) + r')(?!\w)'
    return re.sub(pattern, lambda match: mappings[match.group(0)], text)
