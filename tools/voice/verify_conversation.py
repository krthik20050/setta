"""Live synthetic-input provider smoke. Never records the user's microphone."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from src.sarvam_conversation import SarvamConversation, speech_chunks


def main():
    if '--live' not in sys.argv:
        raise SystemExit('Use --live for the explicitly authorized provider smoke')
    load_dotenv(ROOT/'.env',override=False)
    voice=ROOT/'assets/mother/voice'
    client=SarvamConversation(os.environ['SARVAM_API_KEY'])
    provider=client.reply_provider
    run_name=f'{provider}-conversation-smoke-2026-10-20' if provider!='sarvam' else 'conversation-smoke-2026-10-20'
    out=voice/'experiments'/run_name
    out.mkdir(parents=True,exist_ok=True)
    report=out/'results.json'
    model=client.groq_model if provider=='groq' else client.openai_model if provider=='openai' else client.config['chat_model']
    record=json.loads(report.read_text(encoding='utf-8')) if report.exists() else {'scope':'Synthetic generated inputs; no live microphone or speaker receipt proof','reply_provider':provider,'reply_model':model,'turns':[]}
    try:
        for language in ['ml-IN','en-IN','hi-IN','mixed']:
            if any(t.get('case',t['expected_language'])==language and t['outputs'] for t in record['turns']):
                continue
            expected='ml-IN' if language=='mixed' else language
            source=(voice/'experiments/sarvam-extended-2026-10-20/candidate-6-mixed.wav') if language=='mixed' else voice/f'experiments/sarvam-2026-10-20/clip-6-{language}.wav'
            audio=source.read_bytes()
            if language=='mixed':
                # REST STT accepts short input; use only the first 20 seconds.
                clipped=io.BytesIO()
                with wave.open(io.BytesIO(audio),'rb') as original:
                    with wave.open(clipped,'wb') as target:
                        target.setparams(original.getparams());target.writeframes(original.readframes(original.getframerate()*20))
                audio=clipped.getvalue()
            turn=client.recognize(audio)
            if turn is None: raise RuntimeError('No transcript')
            answer=client.reply(turn)
            row={'case':language,'input_file':str(source),'input_max_seconds':20 if language=='mixed' else None,'expected_language':expected,'detected_language':turn.language,
                 'transcript':turn.text,'language_confidence':turn.confidence,'reply':answer,
                 'reference_clip':client.voice_for(turn,answer)[1],'outputs':[]}
            record['turns'].append(row)
            for index,chunk in enumerate(speech_chunks(answer)):
                audio=client.synthesize(chunk,turn,answer)
                path=out/f'{language}-{index}.wav';path.write_bytes(audio)
                row['outputs'].append({'file':path.name,'text':chunk,'sha256':hashlib.sha256(audio).hexdigest()})
            (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            print(language,'detected',turn.language,'voice',row['reference_clip'],'chunks',len(row['outputs']),flush=True)
            if turn.language!=expected: raise RuntimeError('Synthetic input language mismatch')
            if language=='mixed' and row['reference_clip']!=6: raise RuntimeError('Mixed voice routing mismatch')
    finally:
        client.close()
        (out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
