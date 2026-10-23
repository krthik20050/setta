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
    names=app_names or {'calculator','notepad','file_explorer'}
    labels=sorted(((name.replace('_',' '),name) for name in names), key=lambda item: len(item[0]), reverse=True)
    choices='|'.join(re.escape(label) for label,_ in labels)
    prefix=r'(?:^|[.!?,;]\s*|\b(?:then|and|also|like|uh|um)\s+|\b(?:can|could|would) you\s+|\bplease\s+)'
    match=re.search(prefix+r'(?:please\s+)?(?:open|launch|start|bring up) (?:the )?('+choices+r')(?: app)?(?=$|[.!?,;]|\s+(?:please|now|for me)\b)',text,re.I)
    if match:
        label=match[1].casefold()
        return 'open_app',next(name for display,name in labels if display.casefold()==label)
    match=re.fullmatch(r'(?:please )?(?:search|google|look up|find online)(?: for)? (.+)',text,re.I)
    if match and len(match[1].strip()) <= 240:
        return 'search_browser',match[1].strip()
    return None
