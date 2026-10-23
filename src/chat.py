import re
import json
import urllib.request
from google import genai

SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


def create_client(api_key):
    return genai.Client(api_key=api_key)


def extract_sentences(text):
    parts = SENTENCE_RE.split(text)
    if len(parts) <= 1:
        return [], text
    return parts[:-1], parts[-1]


def chat_with_ai(prompt, api_key="", model="openai/gpt-4o-mini", url="https://openrouter.ai/api/v1/chat/completions"):
    if not api_key:
        return "Error: SETTA_API_KEY not set"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }).encode()
    req = urllib.request.Request(url, data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"
