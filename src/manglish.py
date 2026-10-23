"""Readable Malayalam in Latin letters, only for the display layer."""
import unicodedata

_VOWELS = dict(zip('അആഇഈഉഊഋഌഎഏഐഒഓഔ',
    ('a','aa','i','ee','u','oo','ri','li','e','e','ai','o','o','au')))
_CONSONANTS = dict(zip('കഖഗഘങചഛജഝഞടഠഡഢണതഥദധനപഫബഭമയരലവശഷസഹളഴറ',
    ('k','kh','g','gh','ng','ch','chh','j','jh','nj','t','th','d','dh','n',
     'th','th','d','dh','n','p','ph','b','bh','m','y','r','l','v','sh','sh','s','h','l','zh','r')))
_SIGNS = dict(zip('ാിീുൂൃെേൈൊോൌൗ',
    ('aa','i','ee','u','oo','ri','e','e','ai','o','o','au','au')))
_OTHER = dict(zip('ൺൻർൽൾൿംഃഽ', ('n','n','r','l','l','k','m','h',"'")))
_OTHER.update({'ഩ': 'na', 'ഺ': 'tta', 'ൠ': 'ri', 'ൡ': 'li',
               'ൢ': 'li', 'ൣ': 'li', 'ൎ': 'r', 'ഁ': 'm', 'ഄ': ''})
_OTHER.update({chr(0x0D66 + n): str(n) for n in range(10)})


def to_manglish(text: str) -> str:
    """Preserve English; use phonetic aa/ee/oo vowels for Malayalam."""
    parts = []
    inherent = False
    for char in unicodedata.normalize('NFC', text):
        if char in _CONSONANTS:
            parts.append(_CONSONANTS[char] + 'a')
            inherent = True
        elif char in _SIGNS or char == '്':
            if inherent:
                parts[-1] = parts[-1][:-1]
            parts.append(_SIGNS.get(char, ''))
            inherent = False
        elif char in ('\u200c', '\u200d'):
            continue
        else:
            fallback = ('[' + unicodedata.name(char, 'Malayalam symbol').replace('MALAYALAM ', '').lower() + ']'
                        if '\u0d00' <= char <= '\u0d7f' else char)
            parts.append(_VOWELS.get(char, _OTHER.get(char, fallback)))
            inherent = False
    return ''.join(parts)
