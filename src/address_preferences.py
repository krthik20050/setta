"""Explicit address preferences, separate from conversation language and identity."""
import re

MONE='\u0d2e\u0d4b\u0d28\u0d47'


def address_request(text,language):
    value=text.strip().rstrip('.!?').strip()
    match=re.fullmatch(r'(?:please\s+|always\s+|from now on[, ]+|I (?:want|would like) you to\s+)?'
        r'(?:call me|address me as)\s+["\x27]?([\w-]{1,40})["\x27]?'
        r'(?:\s*[,;]?\s+(.*))?',value,re.I)
    if not match: return None
    term=match[1]
    # "Call me tomorrow" is a scheduling request, not a new nickname.
    if term.casefold() in {'tomorrow','today','tonight','later','soon','back','now'}:
        return None
    if term.casefold() in {'mone','monne','monwe',MONE}: term='mone'
    suffix=(match[2] or '').casefold()
    if suffix and not re.fullmatch(r'(?:just )?(?:once|this time|for now|from now on|always|in all languages|'
        r'(?:even )?(?:in|when speaking) (?:english|malayalam|hindi)|not son|instead of son)',suffix):
        return None  # Do not save guessed intent from an arbitrary following clause.
    scope='once' if re.search(r'\b(once|this time|for now)\b',suffix) else 'all'
    for word,code in [('english','en-IN'),('malayalam','ml-IN'),('hindi','hi-IN')]:
        if word in suffix: scope=code
    return {'term':term,'scope':scope,'source':'explicit_user_request'}


def resolve_address(facts,language):
    keys={'preferred_address','preferred_address_'+language}
    candidates=[row for row in facts if row.get('key') in keys]
    if not candidates: return None
    row=max(candidates,key=lambda row:(row.get('updated_at',''),row.get('source_message_id',0)))
    term=row.get('value','')
    return {'term':term,'scope':language if row['key'].endswith(language) else 'all',
        'source':'saved_user_preference'} if isinstance(term,str) and 0<len(term)<=40 else None


def address_segments(text,language,preference):
    if not preference or preference.get('term','').casefold()!='mone':
        return [(text,language)]
    if language=='ml-IN':
        return [(re.sub(r'(?<!\w)mone(?!\w)',MONE,text,flags=re.I),language)]
    matches=list(re.finditer(r'(?<!\w)mone(?!\w)',text,re.I))
    if not matches: return [(text,language)]
    if len(matches)>2: raise ValueError('The reply repeats the address too many times')
    result=[]; offset=0
    for match in matches:
        before=text[offset:match.start()]
        if any(c.isalnum() for c in before): result.append((before,language))
        result.append((MONE,'ml-IN'))
        offset=match.end()
    after=text[offset:]
    if any(c.isalnum() for c in after): result.append((after.lstrip(' ,.!'),language))
    return result
