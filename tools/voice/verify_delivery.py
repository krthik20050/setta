"""Opt-in live provider check using synthetic text; never opens the microphone."""
import io
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from src.manglish import to_manglish
from src.sarvam_conversation import SarvamConversation, RecognizedTurn
import os


def duration(audio):
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        return round(wav.getnframes() / wav.getframerate(), 3)


def main():
    load_dotenv(ROOT/'.env')
    out = ROOT/'assets/mother/voice/experiments/conversational-delivery-2026-10-20'
    out.mkdir(parents=True, exist_ok=True)
    client = SarvamConversation(os.environ['SARVAM_API_KEY'], openai_api_key='')
    rows = []
    try:
        for language, prompt in [
            ('ml-IN', '\u0d05\u0d2e\u0d4d\u0d2e\u0d47, \u0d07\u0d28\u0d4d\u0d28\u0d4d \u0d0e\u0d28\u0d4d\u0d31\u0d46 \u0d2a\u0d30\u0d40\u0d15\u0d4d\u0d37 \u0d28\u0d28\u0d4d\u0d28\u0d3e\u0d2f\u0d3f \u0d2a\u0d4b\u0d2f\u0d3f!'),
            ('hi-IN', 'Maa, aaj mera exam bahut achha gaya!'),
            ('en-IN', 'Amma, my exam went really well today!'),
        ]:
            client.history = []
            turn = RecognizedTurn(prompt, language, None, False)
            reply = client.reply(turn)
            audio = client.synthesize(reply, turn)
            name = language + '-pace-1.18.wav'
            (out/name).write_bytes(audio)
            row = {'language': language, 'display_reply': to_manglish(reply),
                   'reference_clip': client.voice_for(turn, reply)[1],
                   'pace': 1.18, 'file': name, 'seconds': duration(audio)}
            if language == 'ml-IN':
                client.profile.data['speech_delivery']['pace'] = 1.0
                baseline = client.synthesize(reply, turn)
                client.profile.data['speech_delivery']['pace'] = 1.18
                (out/'ml-IN-pace-1.0.wav').write_bytes(baseline)
                row['baseline_file'] = 'ml-IN-pace-1.0.wav'
                row['baseline_seconds'] = duration(baseline)
            rows.append(row)
            (out/'results.json').write_text(json.dumps({
                'scope': 'Live Groq and Sarvam synthetic text check; not microphone or human listening verification.',
                'turns': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(language, row['seconds'], 'seconds', flush=True)
    finally:
        client.close()


if __name__ == '__main__':
    main()
