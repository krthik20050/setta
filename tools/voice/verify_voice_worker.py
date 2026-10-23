"""Run the real voice worker with synthetic mic input and simulated playback.

Provider calls are live; no physical microphone or speakers are activated.
"""
from pathlib import Path
import io
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
import speech_recognition as sr
from src.live_conversation import LiveConversation
from src.sarvam_voice import SarvamVoiceAgent


def main():
    if '--live' not in sys.argv:
        raise SystemExit('Use --live to authorize provider calls with synthetic input')
    load_dotenv(ROOT/'.env',override=False)
    source=ROOT/'assets/mother/voice/experiments/sarvam-2026-10-20/clip-6-en-IN.wav'
    with wave.open(str(source),'rb') as wav:
        captured=sr.AudioData(wav.readframes(wav.getnframes()),wav.getframerate(),wav.getsampwidth())
    recognizer=MagicMock();recognizer.listen.return_value=captured
    states=[];played=[];errors=[]
    agent=SarvamVoiceAgent(os.environ['SARVAM_API_KEY']);agent.muted=False;agent.active=True
    agent.on_state_change=states.append
    def final(text):
        if text.startswith('Voice mode stopped'): errors.append(text)
        agent.stop()
    agent.on_text_final=final
    def playback(path,flags):
        if path:
            with wave.open(path,'rb') as wav:
                played.append({'frames':wav.getnframes(),'sample_rate':wav.getframerate()})
    with tempfile.TemporaryDirectory(dir=ROOT/'.tools') as directory:
        def conversation(key,observations):
            return LiveConversation(key,memory_path=Path(directory)/'worker.sqlite',observations=observations)
        with patch('src.sarvam_voice.LiveConversation',side_effect=conversation), \
             patch('src.sarvam_voice.sr.Microphone',return_value=MagicMock()), \
             patch('src.sarvam_voice.sr.Recognizer',return_value=recognizer), \
             patch('src.sarvam_voice.winsound.PlaySound',side_effect=playback), \
             patch.object(agent._stop,'wait',return_value=False):
            agent._run()
    report={'scope':'Real worker and live providers; synthetic microphone and simulated Windows playback',
        'states':states,'playback_chunks':played,'worker_error':bool(errors),
        'physical_mic_or_speaker_proof':False,'stopped_after_one_turn':not agent.active}
    (ROOT/'runtime/voice-worker-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if errors or not played or 'talk' not in states:
        raise SystemExit('Voice worker smoke failed; inspect stage/type diagnostic')


if __name__=='__main__': main()
