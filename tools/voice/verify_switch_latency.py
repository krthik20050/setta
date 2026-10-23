"""Opt-in synthetic provider test: language switching and stage timings."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from src.live_conversation import LiveConversation
from src.manglish import to_manglish
from src.sarvam_conversation import RecognizedTurn, speech_chunks


def main():
    load_dotenv(ROOT/'.env')
    out = ROOT/'assets/mother/voice/experiments/language-switch-latency-2026-10-20'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as folder:
        client = LiveConversation(os.environ['SARVAM_API_KEY'], memory_path=Path(folder)/'synthetic.sqlite')
        try:
            for index, (language, text) in enumerate([
                ('ml-IN', '\u0d05\u0d2e\u0d4d\u0d2e\u0d47, \u0d07\u0d28\u0d4d\u0d28\u0d4d \u0d1e\u0d3e\u0d28\u0d4d\u200d \u0d15\u0d4b\u0d21\u0d4d \u0d0e\u0d34\u0d41\u0d24\u0d41\u0d15\u0d2f\u0d3e\u0d23\u0d4d.'),
                ('en-IN', 'Switch to English now. I am just fixing a small bug, no big deal.'),
                ('hi-IN', 'Ab Hindi mein baat karo. Bas thoda kaam baaki hai.'),
                ('en-IN', 'Back to English please. Keep it casual and brief.'),
            ]):
                started = time.monotonic()
                turn = RecognizedTurn(text, language, None, False)
                reply = client.reply(turn)
                reply_seconds = time.monotonic()-started
                chunks = speech_chunks(reply)
                audio_started = time.monotonic()
                audio = client.synthesize(chunks[0], turn, reply)
                tts_seconds = time.monotonic()-audio_started
                name = f'{index+1}-{language}.wav'
                (out/name).write_bytes(audio)
                with wave.open(io.BytesIO(audio), 'rb') as wav:
                    seconds = wav.getnframes()/wav.getframerate()
                row = {'language':language,'reply':to_manglish(reply),
                    'reply_seconds':round(reply_seconds,3),'first_chunk_synthesis_seconds':round(tts_seconds,3),
                    'reply_to_audio_ready_seconds':round(time.monotonic()-started,3),
                    'file':name,'audio_seconds':round(seconds,3),'chunks':len(chunks),
                    'reference_clip':client.voice_for(turn,reply)[1],
                    'pace':client.profile.data.get('speech_delivery',{}).get('pace'), 'enable_qc':False}
                if language == 'ml-IN':
                    selected = client.config['voices']['ml-IN']
                    client.config['voices']['ml-IN'] = client.config['voices']['malayalam_mixed']
                    try:
                        comparison = client.synthesize(chunks[0], turn, reply)
                        (out/'malayalam-reference-6-comparison.wav').write_bytes(comparison)
                        row['texture_comparison_file'] = 'malayalam-reference-6-comparison.wav'
                    finally:
                        client.config['voices']['ml-IN'] = selected
                if language == 'en-IN' and index == 1:
                    client.profile.data['speech_delivery']['enable_qc'] = True
                    baseline_started = time.monotonic()
                    baseline = client.synthesize(chunks[0], turn, reply)
                    row['qc_enabled_synthesis_seconds'] = round(time.monotonic()-baseline_started,3)
                    client.profile.data['speech_delivery']['enable_qc'] = False
                    (out/'english-qc-enabled.wav').write_bytes(baseline)
                rows.append(row)
                (out/'results.json').write_text(json.dumps({'scope':
                    'Synthetic text through live Groq/Sarvam with isolated persistent memory. No microphone, camera, screen or speaker receipt test.',
                    'turns':rows},ensure_ascii=False,indent=2),encoding='utf-8')
                print(language, row['reply_to_audio_ready_seconds'], 'seconds to audio ready',flush=True)
        finally:
            client.close()


if __name__ == '__main__':
    main()
