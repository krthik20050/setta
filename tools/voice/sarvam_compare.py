"""Create three consented candidate voices and a bounded multilingual comparison.

Keys remain in .env/environment. No automatic retries of billable POST requests.
Reruns reuse locally recorded voice IDs and validated outputs.
"""
import base64
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys
import wave

from dotenv import load_dotenv
import httpx
import os

ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / 'assets/mother/voice'
OUT = VOICE / 'experiments/sarvam-2026-10-20'
TEXTS = {
    'en-IN': 'Hello, how was your day? Take your time. Let us learn something new together.',
    'ml-IN': 'ഇന്ന് നിന്റെ ദിവസം എങ്ങനെയുണ്ടായിരുന്നു? പതുക്കെ മതി. നമുക്ക് ഒരുമിച്ച് പുതിയൊരു കാര്യം പഠിക്കാം.',
    'hi-IN': 'आज तुम्हारा दिन कैसा रहा? आराम से बोलो। चलो, हम साथ मिलकर कुछ नया सीखते हैं।',
}


def save(record: dict) -> None:
    temp = OUT / 'experiment.tmp'
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(OUT / 'experiment.json')


def request(client: httpx.Client, endpoint: str, fields: dict, file: Path | None = None) -> dict:
    # Force multipart even when referencing a saved voice without a file.
    parts = [(k, (None, str(v))) for k, v in fields.items()]
    if file is not None:
        with file.open('rb') as source:
            response = client.post(endpoint, files=parts + [('file', (file.name, source, 'audio/wav'))])
    else:
        response = client.post(endpoint, files=parts)
    if not response.is_success:
        # Never print headers, credentials, or complete response data.
        raise RuntimeError(f'{endpoint} returned HTTP {response.status_code}: '
                           + response.text.replace(client.headers['api-subscription-key'], '[REDACTED]')[:600])
    return response.json()


def page(record: dict) -> None:
    cards = []
    for ref in record['references']:
        players = []
        for result in ref.get('outputs', []):
            players.append(f"<p><b>{html.escape(result['language'])}</b>: {html.escape(result['text'])}</p>"
                           f"<audio controls preload='none' src='{html.escape(result['file'])}'></audio>")
        cards.append(f"<article><h2>Reference clip {ref['rank']}</h2>"
                     f"<p>Original reference</p><audio controls preload='none' src='../../references/approved-2026-10-20/{html.escape(Path(ref['reference_path']).name)}'></audio>"
                     + ''.join(players) + '</article>')
    (OUT/'listen.html').write_text("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>Sarvam voice comparison</title><style>body{font:17px/1.6 system-ui;max-width:850px;margin:40px auto;padding:0 20px;background:#faf9f6;color:#242424}audio{width:100%}article{border-bottom:1px solid #ccc;padding:20px 0}</style>"
        "<h1>Sarvam generated voice comparison</h1><p>Generated synthetic speech. Compare each version against the original. No winner has been selected. Judge voice resemblance, pronunciation, rhythm and artifacts separately.</p>"
        + ''.join(cards),encoding='utf-8')


def main() -> None:
    load_dotenv(ROOT / '.env', override=False)
    key = os.environ.get('SARVAM_API_KEY', '').strip()
    if not key:
        raise RuntimeError('SARVAM_API_KEY is missing')
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'experiment.json'
    if path.exists():
        record = json.loads(path.read_text(encoding='utf-8'))
    else:
        record = dict(started_utc=datetime.now(timezone.utc).isoformat(), provider='Sarvam',
                      base_url='https://api.sarvam.ai', status='prepared', texts=TEXTS,
                      consent='User confirmed mother consent and selected clips 6, 7, 8.', references=[])
    approved = json.loads((VOICE/'references/approved-2026-10-20/manifest.json').read_text(encoding='utf-8-sig'))
    if sum(len(t) for t in TEXTS.values())*3 > 1500:
        raise RuntimeError('Comparison exceeded the planned 1500-character generation limit')
    save(record)
    with httpx.Client(base_url='https://api.sarvam.ai', headers={'api-subscription-key':key},
                      timeout=httpx.Timeout(180,connect=30),follow_redirects=False) as client:
        for source in approved['references']:
            reference = Path(source['approved_reference_path'])
            digest = hashlib.sha256(reference.read_bytes()).hexdigest().upper()
            if digest != source['sha256']:
                raise RuntimeError('Approved reference checksum changed')
            ref = next((r for r in record['references'] if r['rank']==source['rank']),None)
            if ref is None:
                ref = dict(rank=source['rank'],reference_path=str(reference),sha256=digest,
                           name=f"setta-mother-ref-{source['rank']}-20261020",outputs=[])
                record['references'].append(ref)
            if not ref.get('voice_id'):
                # Mark request before sending: interrupted creations need reconciliation,
                # not blind retries which could create duplicate voices/charges.
                if ref.get('create_status')=='request_started':
                    raise RuntimeError('Previous creation interrupted; reconcile voice list before retrying')
                ref['create_status']='request_started'; save(record)
                response = request(client,'/voices/create',dict(name=ref['name'],language='en-IN',style='conversational'),reference)
                data = response.get('data',{})
                if not data.get('voice_id'):
                    raise RuntimeError('Create response missing voice_id; inspect account before retrying')
                ref.update(voice_id=data['voice_id'],create_status='saved',
                           provider_reference_text=data.get('reference_text'),provider_status=data.get('status'))
                save(record)
                print('Created candidate for clip',source['rank'],flush=True)
            for language,text in TEXTS.items():
                if any(r['language']==language for r in ref['outputs']):
                    continue
                record['pending_generation']=dict(rank=ref['rank'],language=language)
                save(record)
                response = request(client,'/voices/clone',dict(voice_id=ref['voice_id'],text=text,
                    language_code=language,output_audio_codec='wav',speech_sample_rate=24000,enable_qc='true'))
                audio = base64.b64decode(response.get('audio_b64') or response.get('audio') or '',validate=True)
                output = OUT/f"clip-{ref['rank']}-{language}.wav"
                if not audio:
                    raise RuntimeError('Provider returned empty audio')
                output.write_bytes(audio)
                with wave.open(str(output),'rb') as wav:
                    duration=wav.getnframes()/wav.getframerate()
                    if duration<=0:
                        raise RuntimeError('Generated WAV has no frames')
                    rate=wav.getframerate()
                ref['outputs'].append(dict(language=language,text=text,file=output.name,
                    request_id=response.get('request_id'),sha256=hashlib.sha256(audio).hexdigest(),
                    duration_seconds=duration,sample_rate=rate,enable_qc=True))
                record.pop('pending_generation',None);save(record);page(record)
                print('Generated clip',ref['rank'],language,round(duration,2),'seconds',flush=True)
    record['status']='generated_awaiting_human_comparison'
    record['finished_utc']=datetime.now(timezone.utc).isoformat()
    save(record);page(record)


if __name__=='__main__':
    try:
        main()
    except (httpx.HTTPError,RuntimeError,ValueError,OSError) as error:
        load_dotenv(ROOT/'.env',override=False)
        message=str(error)
        secret=os.environ.get('SARVAM_API_KEY','')
        if secret:
            message=message.replace(secret,'[REDACTED]')
        if OUT.exists():
            (OUT/'last-error.txt').write_text(message,encoding='utf-8')
        print(message,file=sys.stderr)
        sys.exit(1)
