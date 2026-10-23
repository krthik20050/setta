"""Real Sarvam recall check; synthetic text only, no recording or playback."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from src.live_conversation import LiveConversation
from src.sarvam_conversation import RecognizedTurn

def main():
    if '--live' not in sys.argv:
        raise SystemExit('Pass --live to call the configured Sarvam provider')
    load_dotenv(ROOT/'.env', override=False)
    key = os.environ.get('SARVAM_API_KEY', '').strip()
    if not key:
        raise SystemExit('SARVAM_API_KEY is unavailable')
    folder = ROOT/'runtime'/'live-memory-checks'/str(uuid4())
    folder.mkdir(parents=True)
    token = 'Jasmine-' + uuid4().hex[:8]
    result = {'provider':'Sarvam', 'scope':'synthetic text; no microphone, synthesis or playback',
              'restarted_session_recall':False}
    first = LiveConversation(key, memory_path=folder/'memory.sqlite', session_id='first')
    try:
        first.reply(RecognizedTurn(f'For this test, my project codename is {token}. Remember it.', 'en-IN', None, False))
    finally:
        first.close()
    second = LiveConversation(key, memory_path=folder/'memory.sqlite', session_id='after-restart')
    try:
        reply = second.reply(RecognizedTurn('What is my project codename? Reply with the codename.', 'en-IN', None, False))
        result['restarted_session_recall'] = token.casefold() in reply.casefold()
        result['stored_messages'] = len(second.memory.recent())
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
        if not result['restarted_session_recall']:
            raise SystemExit('Recall check failed')
    finally:
        second.close()
if __name__=='__main__': main()
