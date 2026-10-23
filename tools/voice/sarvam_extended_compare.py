"""Bounded follow-up comparison using the two existing preferred Sarvam voices."""
import base64
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import sys
import wave

from dotenv import load_dotenv
import httpx
from sarvam_compare import request

ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT/'assets/mother/voice'
OUT = VOICE/'experiments/sarvam-extended-2026-10-20'
PASSAGES = {
    'malayalam': {
        'label': 'Longer Malayalam conversation',
        'language': 'ml-IN',
        'text': 'ഇന്ന് എന്തൊക്കെയാണ് പഠിച്ചത്? എല്ലാം ഒറ്റ ദിവസം കൊണ്ട് മനസ്സിലാക്കണം എന്നില്ല. ആദ്യം പാഠം പതുക്കെ വായിക്കൂ. മനസ്സിലാകാത്ത ഭാഗം വന്നാൽ ചോദിക്കണം. തെറ്റ് പറ്റിയാലും വിഷമിക്കേണ്ട. വീണ്ടും ശ്രമിച്ചാൽ മതി. കുറച്ചു നേരം വിശ്രമിച്ചിട്ട് നമുക്ക് ബാക്കി ഒരുമിച്ച് പഠിക്കാം. പഠിക്കുന്ന കാര്യങ്ങൾ സ്വന്തം വാക്കുകളിൽ പറഞ്ഞുനോക്കുന്നത് ഓർമ്മിക്കാൻ സഹായിക്കും.',
    },
    'mixed': {
        'label': 'Malayalam with English switching',
        'language': 'ml-IN',
        'text': 'ഇന്ന് നമുക്ക് subject verb agreement പഠിക്കാം. The girl reads a book. ഇവിടെ girl singular ആയതുകൊണ്ട് reads എന്നാണ് പറയുന്നത്. ഇനി The girls read books എന്ന് നോക്കൂ. ഇവിടെ subject plural ആണ്, അതുകൊണ്ട് read ഉപയോഗിക്കുന്നു. ഈ രണ്ട് sentences തമ്മിലുള്ള difference മനസ്സിലായോ? Take your time. ആദ്യം നീ ഒന്ന് ശ്രമിക്കൂ, പിന്നെ നമുക്ക് answer ഒരുമിച്ച് നോക്കാം.',
    },
}


def save(record: dict) -> None:
    temporary = OUT/'experiment.tmp'
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(OUT/'experiment.json')


def render(record: dict) -> None:
    cards=[]
    for name, passage in PASSAGES.items():
        players=[]
        for rank in (6,8):
            output=next((r for r in record['outputs'] if r['rank']==rank and r['passage']==name),None)
            if output:
                players.append(f"<section><h3>Candidate {rank}</h3><audio controls preload='none' src='{output['file']}'></audio></section>")
        cards.append(f"<article><h2>{html.escape(passage['label'])}</h2><p lang='ml'>{html.escape(passage['text'])}</p><div class='pair'>{''.join(players)}</div></article>")
    originals=[]
    for reference in record['voices']:
        filename=html.escape(Path(reference['reference_path']).name)
        originals.append(f"<section><h3>Original clip {reference['reference_clip']}</h3><audio controls preload='none' src='../../references/approved-2026-10-20/{filename}'></audio></section>")
    page="""<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>Mother voice — candidates 6 and 8</title><style>body{font:17px/1.65 system-ui;max-width:1000px;margin:40px auto;padding:0 24px;background:#faf9f6;color:#242424}h1{line-height:1.2}.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px}audio{width:100%}article{border-top:1px solid #ccc;padding:25px 0}p[lang]{line-height:1.95}button{padding:10px 18px;font:inherit;margin:8px 0}label{display:block;padding:6px 0}@media(max-width:650px){.pair{grid-template-columns:1fr}}</style>
<h1>Compare candidates 6 and 8</h1><p>Generated synthetic speech using your two preferred voices. Play the same passage from each candidate. Listen for familiar tone, natural Malayalam, English pronunciation, smooth transitions and consistency near the end.</p>
<h2>Original references</h2><div class='pair'>"""+''.join(originals)+"</div>"+''.join(cards)+"""
<article><h2>Your listening notes</h2><p>These notes save automatically in this browser. Download the review to keep a separate copy, or tell me your choice in chat.</p>
<label>Preferred Malayalam version: <select id='malayalam'><option value=''>Not chosen</option><option>6</option><option>8</option><option>Both similar</option><option>Neither</option></select></label>
<label>Preferred mixed-language version: <select id='mixed'><option value=''>Not chosen</option><option>6</option><option>8</option><option>Both similar</option><option>Neither</option></select></label>
<label>Comments<br><textarea id='notes' rows='4' style='width:100%;font:inherit'></textarea></label><button id='download'>Download my review</button><p id='status' aria-live='polite'></p></article>
<script>const key='setta-sarvam-extended-20261020';const ids=['malayalam','mixed','notes'];let prior={};try{prior=JSON.parse(localStorage.getItem(key)||'{}')}catch{}for(const id of ids){const el=document.getElementById(id);el.value=prior[id]||'';el.addEventListener('input',()=>{const data=Object.fromEntries(ids.map(k=>[k,document.getElementById(k).value]));try{localStorage.setItem(key,JSON.stringify(data));document.getElementById('status').textContent='Saved in this browser.'}catch{document.getElementById('status').textContent='Browser saving unavailable. Download your review instead.'}})}document.getElementById('download').onclick=()=>{const data=Object.fromEntries(ids.map(k=>[k,document.getElementById(k).value]));const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mother-voice-extended-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};</script></html>"""
    (OUT/'listen.html').write_text(page,encoding='utf-8')


def main() -> None:
    load_dotenv(ROOT/'.env',override=False)
    key=os.environ.get('SARVAM_API_KEY','').strip()
    if not key:
        raise RuntimeError('SARVAM_API_KEY not configured')
    voices=json.loads((VOICE/'experiments/sarvam-2026-10-20/user-preferences.json').read_text(encoding='utf-8'))['preferred_candidates']
    if {v['reference_clip'] for v in voices}!={6,8}:
        raise RuntimeError('Expected exactly the two approved candidates')
    if any(len(p['text'])>1000 for p in PASSAGES.values()) or sum(len(p['text']) for p in PASSAGES.values())*2>2000:
        raise RuntimeError('Passages exceed the bounded experiment size')
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'experiment.json'
    record=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(
        started_utc=datetime.now(timezone.utc).isoformat(),provider='Sarvam',
        voices=voices,passages=PASSAGES,outputs=[],status='prepared',
        settings=dict(language_code='ml-IN',output_audio_codec='wav',speech_sample_rate=24000,enable_qc=True))
    if record.get('pending_request'):
        raise RuntimeError('Previous request interrupted; review records before retrying a billable request')
    save(record)
    with httpx.Client(base_url='https://api.sarvam.ai',headers={'api-subscription-key':key},
                      timeout=httpx.Timeout(240,connect=30),follow_redirects=False) as client:
        for voice in voices:
            source=Path(voice['reference_path'])
            if hashlib.sha256(source.read_bytes()).hexdigest().upper()!=voice['reference_sha256']:
                raise RuntimeError('Approved reference changed')
            rank=voice['reference_clip']
            for name,passage in PASSAGES.items():
                if any(o['rank']==rank and o['passage']==name for o in record['outputs']):
                    continue
                record['pending_request']=dict(rank=rank,passage=name);save(record)
                response=request(client,'/voices/clone',dict(voice_id=voice['voice_id'],text=passage['text'],
                    language_code=passage['language'],output_audio_codec='wav',speech_sample_rate=24000,enable_qc='true'))
                audio=base64.b64decode(response.get('audio_b64') or response.get('audio') or '',validate=True)
                output=OUT/f'candidate-{rank}-{name}.wav';output.write_bytes(audio)
                with wave.open(str(output),'rb') as wav:
                    duration=wav.getnframes()/wav.getframerate()
                    if duration<=0: raise RuntimeError('Empty generated WAV')
                record['outputs'].append(dict(rank=rank,voice_id=voice['voice_id'],passage=name,text=passage['text'],
                    language_code=passage['language'],file=output.name,request_id=response.get('request_id'),
                    duration_seconds=duration,sha256=hashlib.sha256(audio).hexdigest()))
                record.pop('pending_request');save(record);render(record)
                print('Generated candidate',rank,name,round(duration,2),'seconds',flush=True)
    record['status']='generated_awaiting_user_review';record['finished_utc']=datetime.now(timezone.utc).isoformat()
    save(record);render(record)


if __name__=='__main__':
    try:
        main()
    except (httpx.HTTPError,RuntimeError,ValueError,OSError) as error:
        message=str(error);secret=os.environ.get('SARVAM_API_KEY','')
        if secret: message=message.replace(secret,'[REDACTED]')
        if OUT.exists(): (OUT/'last-error.txt').write_text(message,encoding='utf-8')
        print(message,file=sys.stderr);sys.exit(1)
