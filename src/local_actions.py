"""Deterministic arithmetic and explicit local commands; never evaluate Python code."""
import ast
import operator
import re
import subprocess
import json
from .paths import PROJECT_ROOT


def calculate(expression):
    expression=expression.strip().replace('×','*').replace('÷','/')
    if len(expression)>160 or not re.fullmatch(r'[\d\s.+*/()\-]+',expression):
        raise ValueError('Use a short numeric expression with +, -, *, / and parentheses')
    try: tree=ast.parse(expression,mode='eval')
    except SyntaxError: raise ValueError('The arithmetic expression is incomplete') from None
    if sum(1 for _ in ast.walk(tree))>65: raise ValueError('Expression is too complex')
    binary={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float): value=node.value
        elif isinstance(node,ast.BinOp) and type(node.op) in binary:
            value=binary[type(node.op)](visit(node.left),visit(node.right))
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand)*(-1 if isinstance(node.op,ast.USub) else 1)
        else: raise ValueError('Unsupported arithmetic')
        import math
        if not math.isfinite(value) or abs(value)>1e15: raise ValueError('Result is outside the supported range')
        return value
    try: value=visit(tree.body)
    except (ZeroDivisionError,OverflowError,RecursionError): raise ValueError('This calculation cannot be completed') from None
    return format(value,'.12g')


def calculator(expression):
    result=calculate(expression)
    # This adapter deliberately supports only simple nonnegative operands;
    # more complex expressions still have a verified local arithmetic answer.
    if not re.fullmatch(r'\d+(?:\.\d+)?\s*[+*/-]\s*\d+(?:\.\d+)?',expression):
        return {'status':'local_only','result':result,'calculator_verified':False}
    try:
        completed=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            str(PROJECT_ROOT/'tools/calculator-action.ps1'),'-Expression',expression],
            capture_output=True,text=True,timeout=18,creationflags=subprocess.CREATE_NO_WINDOW)
        data=json.loads(completed.stdout.strip())
        display=str(data.get('display',''))
        numbers=re.findall(r'-?\d[\d,. ]*',display)
        verified=bool(numbers) and numbers[-1].replace(',','').replace(' ','').rstrip('.')==result
        return {'status':'verified' if verified else 'local_only','result':result,
            'calculator_verified':verified,'calculator_display':display[:200]}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {'status':'local_only','result':result,'calculator_verified':False}


def parse_command(text, app_names=None):
    text=text.strip().rstrip('?.!').strip()
    for word,symbol in [('multiplied by','*'),('divided by','/'),('times','*'),('plus','+'),('minus','-')]:
        text=re.sub(r'\b'+word+r'\b',symbol,text,flags=re.I)
    match=re.fullmatch(r'(?:please )?(?:open (?:the )?calculator and (?:calculate|compute)|use (?:the )?calculator (?:to calculate|for)) (.+)',text,re.I)
    if match: return 'calculator',match[1]
    match=re.fullmatch(r'(?:please )?(?:calculate|compute|what is|what\x27s) ([\d\s.+*/()×÷\-]+)',text,re.I)
    if match: return 'calculate',match[1]
    match=re.fullmatch(r'(?:please )?(?:set|start) (?:a )?(\d+(?:\.\d+)?) (second|minute|hour)s? timer',text,re.I)
    if match: return 'timer',float(match[1])*{'second':1,'minute':60,'hour':3600}[match[2].lower()]
    names=app_names if app_names is not None else {'calculator','notepad','file_explorer'}
    labels=sorted(((re.sub(r'[_-]+',' ',str(name)).strip(),name) for name in names),
                  key=lambda item: (-len(item[0]),item[0].casefold(),str(item[1]).casefold()))
    launch=r'(?:open|launch|start|bring up|pull up|run|show me|take me to)'
    prefix=r'(?:^|[.!?,;]\s*|\b(?:then|and|also|like|uh|um)\s+|\b(?:can|could|would|will)(?:\s+(?:you|u))?\s+|\bplease\s+|\bamma\s+)'
    request=re.search(prefix+r'(?:please\s+)?'+launch+r'\s+(?:(?:the|my|me|like)\s+)*(.+)$',text,re.I)
    if request:
        requested=re.sub(r'[.!?,;]+$','',request.group(1).strip())
        requested=re.sub(r'\s+(?:please|now|for me)$','',requested,flags=re.I)
        requested=re.sub(r'\s+(?:app|application|program)$','',requested,flags=re.I)
        normalized=re.sub(r'[^a-z0-9]+',' ',requested.casefold()).strip()
        matches=[]
        partial_matches=[]
        for display,name in labels:
            candidate=re.sub(r'[^a-z0-9]+',' ',display.casefold()).strip()
            if candidate==normalized:
                matches.append(name)
            elif candidate.startswith(normalized) or normalized in candidate:
                partial_matches.append(name)
        exact=[name for display,name in labels
               if re.sub(r'[^a-z0-9]+',' ',display.casefold()).strip()==normalized]
        if exact:
            matches=exact
        elif len(matches)==0:
            matches=partial_matches
        elif partial_matches:
            matches.extend(partial_matches)
        if len(matches)==1:
            return 'open_app',matches[0]
        if len(matches)>1:
            return 'choose_app',tuple(matches)
    # A bare app name in a conversation is commonly an elliptical launch
    # request ("Docker Desktop"). Resolve only exact catalog-name matches.
    bare=re.sub(r'[^a-z0-9]+',' ',text.casefold()).strip()
    exact=[name for display,name in labels
           if re.sub(r'[^a-z0-9]+',' ',display.casefold()).strip()==bare]
    if len(exact)==1:
        return 'open_app',exact[0]
    if len(exact)>1:
        return 'choose_app',tuple(exact)
    match=re.fullmatch(r'(?:please )?(?:search|google|look up|find online)(?: for)? (.+)',text,re.I)
    if match and len(match[1].strip()) <= 240:
        return 'search_browser',match[1].strip()
    return None


def is_app_open_request(text):
    """Recognize an explicit app-opening request even when its target is a category."""
    value=text.strip()
    launch=r'(?:open|launch|start|bring up|pull up|run|show me|take me to)'
    prefix=r'(?:^|[.!?,;]\s*|\b(?:then|and|also|like|uh|um)\s+|\b(?:can|could|would|will)(?:\s+(?:you|u))?\s+|\bplease\s+|\bamma\s+)'
    return bool(re.search(prefix+r'(?:please\s+)?'+launch+r'\s+\S',value,re.I) or
        re.search(r'\b(?:thurakku|thurakkuka|thurakkam|thudangu|thudanguka|kholo|kholiye|kholna|'
                  r'shuru\s+karo|chalu\s+karo|start\s+karo|open\s+cheyyu)\b|'
                  r'\u0916\u094b\u0932|\u0936\u0941\u0930\u0942\s*\u0915\u0930|'
                  r'\u091a\u093e\u0932\u0942\s*\u0915\u0930|\u0d24\u0d41\u0d31|'
                  r'\u0d24\u0d41\u0d1f\u0d19\u0d4d\u0d19|\u0d12\u0d2a\u0d4d\u0d2a\u0d7b',value,re.I))


_APP_TASK_ALIASES={
    'code':(
        'code','coding','programming','software development','software engineering','development','develop',
        'कोड','कोडिंग','कोडिंग के लिए','प्रोग्रामिंग','सॉफ्टवेयर डेवलपमेंट',
        'കോഡ്','കോഡിംഗ്','കോഡിങ്ങ്','കോഡിങ്ങ','കോഡിംഗ','പ്രോഗ്രാമിംഗ്','പ്രോഗ്രാമിങ്ങ്','സോഫ്റ്റ്‌വെയർ ഡെവലപ്മെന്റ്'),
    'design':(
        'design','graphic design','ui design','ux design','drawing','creative work',
        'डिजाइन','डिज़ाइन','डिजाइनिंग','ड्रॉइंग','चित्रकारी',
        'ഡിസൈൻ','ഡിസൈന','ഡിസൈ','ഡിസൈനിംഗ്','ചിത്രരചന','വരയ്ക്കൽ'),
    'browser':('browsing','web browsing','internet','ब्राउज़िंग','वेब ब्राउज़िंग','इंटरनेट','ബ്രൗസിംഗ്','വെബ് ബ്രൗസിംഗ്','ഇന്റർനെറ്റ്'),
    'communication':('communication','messaging','chat','meetings','संचार','मैसेजिंग','चैट','बैठकें','ആശയവിനിമയം','മെസേജിംഗ്','ചാറ്റ്','മീറ്റിംഗ്'),
    'music':('music','listening to music','audio','संगीत','गाना सुनना','ഓഡിയോ','സംഗീതം','പാട്ട് കേൾക്കൽ'),
    'video':('video editing','video production','वीडियो एडिटिंग','वीडियो संपादन','വീഡിയോ എഡിറ്റിംഗ്','വീഡിയോ നിർമ്മാണം'),
    'photo':('photo editing','image editing','photography','फोटो एडिटिंग','फोटो संपादन','ഫോട്ടോ എഡിറ്റിംഗ്','ചിത്രം എഡിറ്റിംഗ്'),
    'files':('file management','archives','फ़ाइल प्रबंधन','फाइल मैनेजमेंट','ഫയൽ മാനേജ്മെന്റ്','ആർക്കൈവ്'),
    'notes':('notes','note taking','taking notes','नोट्स','नोट बनाना','नोट्स बनाना','കുറിപ്പുകൾ','നോട്ട്സ്','കുറിപ്പ് എഴുതൽ'),
    'writing':('writing','writing documents','document writing','लेखन','लिखना','दस्तावेज़ लिखना','എഴുത്ത്','എഴുതാൻ','ഡോക്യുമെന്റ് തയ്യാറാക്കൽ'),
    'office':('office work','documents','office','ऑफिस','दफ्तर का काम','कार्यालय का काम','ഓഫീസ്','ഡോക്യുമെന്റുകൾ'),
    'spreadsheet':('spreadsheet','spreadsheets','excel','sheets','स्प्रेडशीट','शीट','എക്സൽ','സ്പ്രെഡ്ഷീറ്റ്','ഷീറ്റുകൾ'),
    'presentation':('presentation','presentations','slides','प्रेजेंटेशन','स्लाइड','स्लाइड्स','പ്രസന്റേഷൻ','സ്ലൈഡുകൾ'),
    'email':('email','e-mail','mail','ईमेल','मेल','ഇമെയിൽ','മെയിൽ'),
    'terminal':('terminal','shell','command line','टर्मिनल','कमांड लाइन','ഷെൽ','ടെർമിനൽ','കമാൻഡ് ലൈൻ'),
    'gaming':('gaming','games','game','गेमिंग','गेम','खेल','ഗെയിമിംഗ്','ഗെയിം','കളി'),
}


def _app_usage_patterns(user_name=None):
    subjects=[r'i']
    if isinstance(user_name,str) and user_name.strip():
        subjects.append(re.escape(user_name.strip()))
    named_subject=re.escape(user_name.strip()) if isinstance(user_name,str) and user_name.strip() else None
    english_subject='(?:'+'|'.join(subjects)+')'
    hindi_subject=r'(?:मैं|mai(?:n)?'+(('|'+named_subject) if named_subject else '')+')'
    malayalam_subject=r'(?:ഞാൻ|njan|njaan'+(('|'+named_subject) if named_subject else '')+')'
    hindi_verb=r'(?:इस्तेमाल|उपयोग|काम\s+में\s+लेना|चलाना|use|istemaal|istemal|upyog|kaam\s+mein\s+lena|chalana)'
    hindi_finish=r'(?:करता|करती|करते|चलाता|चलाती|चलाते|karta|karti|karte|chalata|chalati|chalate)(?:\s+(?:हूँ|हूं|है|हैं|hu|hoon|hun|hain|hai))?'
    malayalam_verb=r'(?:ഉപയോഗിക്കുന്നു|ഉപയോഗിക്കാറുണ്ട്|ഉപയോഗിക്കും|ഉപയോഗിക്കുന്നുണ്ട്|use\s+(?:cheyy(?:unnu|um|unnath)|ചെയ്യ(?:ുന്നു|ും|ുന്നത്))|upayogikk(?:unnu|um|unnath))'
    for pattern,app_group,task_group in (
        (english_subject+r'\s+(?:usually\s+)?uses?\s+(.{1,100}?)\s+(?:for|to)\s+(.{1,100})',1,2),
        (hindi_subject+r'\s+(.{1,100}?)\s+(?:के\s+लिए|ke\s+liye)\s+(.{1,100}?)\s+(?:(?:का|ka|ko)\s+)?'+hindi_verb+r'\s+'+hindi_finish,2,1),
        (r'(.{1,100}?)\s+(?:के\s+लिए|ke\s+liye)\s+'+hindi_subject+r'\s+(.{1,100}?)\s+(?:(?:(?:का|ka)\s+)?'+hindi_verb+r')\s+'+hindi_finish,2,1),
        (hindi_subject+r'\s+(.{1,100}?)\s+(?:को|ko)\s+(.{1,100}?)\s+(?:के\s+लिए|ke\s+liye)\s+'+hindi_verb+r'\s+'+hindi_finish,1,2),
        (hindi_subject+r'\s+(.{1,100}?)\s+(.{1,100}?)\s+(?:के\s+लिए|ke\s+liye)\s+'+hindi_verb+r'\s+'+hindi_finish,1,2),
        (r'(.{1,100}?)\s+(?:ക്കായി|നായി|ിന്|ന്|inu|in)\s+'+malayalam_subject+r'\s+(.{1,100}?)\s+'+malayalam_verb,2,1),
        (malayalam_subject+r'\s+(.{1,100}?)\s+(?:ക്കായി|നായി|ിന്|ന്|inu|in)\s+(.{1,100}?)\s+'+malayalam_verb,2,1),
        (malayalam_subject+r'\s+(.{1,100}?)\s+(.{1,100}?)\s+(?:ക്കായി|നായി|ിന്|ന്|inu|in)\s+'+malayalam_verb,1,2),
        (r'(.{1,100}?(?:ക്കായി|നായി|ആയി|ക്ക്|ഇന്|ിന്|ന്|inu|in))\s+'+malayalam_subject+r'\s+(.{1,100}?)\s+'+malayalam_verb,2,1),
        (malayalam_subject+r'\s+(.{1,100}?(?:ക്കായി|നായി|ആയി|ക്ക്|ഇന്|ിന്|ന്|inu|in))\s+(.{1,100}?)\s+'+malayalam_verb,2,1),
        (malayalam_subject+r'\s+(.{1,100}?)\s+(.{1,100}?(?:ക്കായി|നായി|ആയി|ക്ക്|ഇന്|ിന്|ന്|inu|in))\s+'+malayalam_verb,1,2),
    ):
        yield re.compile(r'^(?:'+pattern+r')$',re.I),app_group,task_group


def parse_app_usage_statement(text, user_name=None, language=None):
    """Extract clear English, Hindi, Malayalam, or romanized self-reports."""
    value=text.strip().rstrip('.!?।').strip()
    prefixes=('remember that ','याद रखना कि ','याद रखो कि ','yaad rakhna ki ','yaad rakho ki ',
              'ഓർമ്മിക്കുക ','ormikkuka ')
    for prefix in prefixes:
        if value.casefold().startswith(prefix.casefold()):
            value=value[len(prefix):].strip()
            break
    for pattern,app_group,task_group in _app_usage_patterns(user_name):
        match=pattern.fullmatch(value)
        if not match:
            continue
        app=match.group(app_group).strip().strip('"\'`')
        app=re.sub(r'\s+(?:का|को|എന്ന|നെ)$','',app,flags=re.I).strip()
        task=match.group(task_group).strip()
        category=normalize_app_task(task,language)
        if app and category:
            return {'category':category,'app':app}
    return None


def normalize_app_task(task, language=None):
    """Map task labels across supported scripts/transliterations; retain unknown labels."""
    task=str(task).casefold().strip()
    task=re.sub(r'\s+(?:के\s+लिए|ke\s+liye)$','',task)
    task=re.sub(r'\s+',' ',task)
    task=re.sub(r'^(?:(?:my|the|open|launch|start|please|usual|usual app|mera|meri|mere|main|njan|njaan|ente|എന്റെ|എൻ്റെ|मेरे|मेरा|मेरी|जो|जिसे|ഞാൻ|നമ്മൾ|app|ऐप|एप|ആപ്പ്|khol|kholo|thurakku|खोल|खोलो|खोलिए|തുറക്കൂ|തുറക്കുക)\s+)+','',task)
    candidates=[task]
    # Malayalam case endings and romanized Manglish suffixes often attach to a task.
    suffixes=('ക്കായി','നായി','ആയി','ിനായി','ിന്','ന്','inu','in')
    suffix=next((suffix for suffix in suffixes if task.endswith(suffix) and len(task)>len(suffix)),None)
    if suffix and (suffix not in {'inu','in'} or language=='ml-IN' or re.search(r'[\u0d00-\u0d7f]',task)):
        candidates.append(task[:-len(suffix)].strip(' -'))
    for candidate in candidates:
        for category,aliases in _APP_TASK_ALIASES.items():
            if candidate in aliases or any(candidate.startswith(alias+' ') for alias in aliases):
                return category
    # Keep arbitrary task names queryable, including native-script labels.
    slug_source=candidates[-1] if language=='ml-IN' or re.search(r'[\u0d00-\u0d7f]',task) else candidates[0]
    slug=re.sub(r'[^\w]+','_',slug_source,flags=re.UNICODE).strip('_')[:48].strip('_')
    return slug or None


def app_task_reference_request(text, language=None):
    """Find a named task in a multilingual request for the app used to do it."""
    value=text.strip().casefold().rstrip('.!?।').strip()
    action=bool(re.search(
        r'(?:\b(?:open|launch|start|bring up|pull up|run|show me|take me to)\b|'
        r'खोल(?:ो|िए|ना)?|शुरू\s*करो|khol(?:o|iye|na)?|kholo|start\s+karo|'
        r'തുറക്ക(?:ൂ|ുക|ാം)?|ഓപ്പൺ\s*ചെയ്യ(?:ൂ|ുക)?|thurakk(?:u|uka|am)?|thudang(?:u|uka)?)',value,re.I))
    if not action:
        return None
    patterns=(
        r'\b(?:app|application|program|software|tool)\s+(?:that\s+)?(?:i|we)\s+(?:usually\s+)?use\s+(?:for|to)\s+(.+)$',
        r'\b(?:app|application|program|software|tool)\s+(?:जिसे|जो)\s+(?:मैं\s+)?(?:use|इस्तेमाल|उपयोग)\s+करता\s+हूँ\s+(.+)$',
        r'\b(?:app|application|program|software|tool)\s+(?:मैं\s+)?(?:use|इस्तेमाल|ഉപയോഗിക്കുന്ന|ഉപയോഗിക്കുന്ന)\s+(.+?)\s+(?:के\s+लिए|ke\s+liye)$',
        r'(?:^|\s)(.+?)\s+(?:के\s+लिए|ke\s+liye)\s+(?:जो\s+)?(?:app|ऐप|एप)\b',
        r'(?:^|\s)(.+?)(?:ക്കായി|നായി|ിന്|ന്|inu|in)\s+(?:ഞാൻ\s+)?(?:ഉപയോഗിക്കുന്ന|use\s+cheyyunna|upayogikkunna)?\s*(?:app|ആപ്പ്)\b',
        r'(?:^|\s)(.+?)\s+(?:ഉപയോഗിക്കുന്ന|use\s+cheyyunna|upayogikkunna)\s+(?:app|ആപ്പ്)\b',
    )
    for pattern in patterns:
        match=re.search(pattern,value,re.I)
        if match:
            task=normalize_app_task(match.group(1),language)
            if task:
                return task
    # A category word alone is not enough ("open code file" is a document request).
    has_app_cue=bool(re.search(
        r'\b(?:app|apps|application|applications|program|programs|software|tool|tools|editor|editors)\b|'
        r'ऐप|एप|प्रोग्राम|सॉफ्टवेयर|टूल|एडिटर|ആപ്പ്|ആപ്പുകൾ|സോഫ്റ്റ്‌വെയർ|ടൂൾ|എഡിറ്റർ',value,re.I))
    if has_app_cue:
        for category,aliases in _APP_TASK_ALIASES.items():
            for alias in sorted(aliases,key=len,reverse=True):
                if re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',value,re.I) or alias in value:
                    return category
    return None


def is_affirmative(text):
    """Accept a short affirmative turn as consent to the immediately pending action."""
    value = re.sub(r"[.!?,]+$", "", text.strip().casefold()).strip()
    return value in {'yes', 'yes please', 'yeah', 'yeah please', 'yep', 'sure', 'go ahead',
                     'do it', 'please do', 'okay', 'ok', 'അതെ', 'ശരി', 'हाँ', 'जी', 'ठीक है'}


def is_negative(text):
    value = re.sub(r"[.!?,]+$", "", text.strip().casefold()).strip()
    return value in {'no', 'no thanks', 'no thank you', 'cancel', 'stop', 'never mind', 'nevermind',
                     'വേണ്ട', 'ഇല്ല', 'नहीं', 'मत करो'}
