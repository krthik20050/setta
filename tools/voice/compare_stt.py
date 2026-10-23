"""Send identical user-exported WAVs to four STT models; never change production STT."""
import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import time

import httpx
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recordings', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root/'.env')
    samples = json.loads(args.recordings.read_text(encoding='utf-8'))['samples']
    if not 1 <= len(samples) <= 30:
        raise ValueError('Use 1 to 30 short recordings')
    results = []
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        for index, sample in enumerate(samples):
            audio = base64.b64decode(sample['audio_b64'], validate=True)
            if len(audio) > 6_000_000 or audio[:4] != b'RIFF':
                raise ValueError('Expected a short WAV recording')
            for provider, model in [('sarvam', 'saaras:v3'), ('sarvam', 'saaras:v4'),
                                    ('groq', 'whisper-large-v3'), ('groq', 'whisper-large-v3-turbo')]:
                row = {'sample': index+1, 'label': sample.get('label', ''), 'expected': sample.get('expected', ''),
                       'sha256': hashlib.sha256(audio).hexdigest(), 'provider': provider, 'model': model}
                key = os.environ.get('SARVAM_API_KEY' if provider == 'sarvam' else 'GROQ_API_KEY', '')
                if not key:
                    row['status'] = 'missing_key'; results.append(row); continue
                started = time.perf_counter()
                try:
                    if provider == 'sarvam':
                        response = client.post('https://api.sarvam.ai/speech-to-text', headers={'api-subscription-key': key},
                            files={'file': ('phrase.wav', audio, 'audio/wav')},
                            data={'model': model, 'language_code': 'unknown', 'mode': 'codemix'})
                    else:
                        response = client.post('https://api.groq.com/openai/v1/audio/transcriptions', headers={'Authorization': 'Bearer '+key},
                            files={'file': ('phrase.wav', audio, 'audio/wav')},
                            data={'model': model, 'response_format': 'verbose_json', 'temperature': '0'})
                    row.update(seconds=round(time.perf_counter()-started, 3), status=response.status_code)
                    if response.is_success:
                        data = response.json()
                        row.update(transcript=data.get('transcript', data.get('text', '')), language=data.get('language_code', data.get('language')))
                    else:
                        row['retry_after'] = response.headers.get('retry-after')
                except httpx.HTTPError as exc:
                    row.update(status=type(exc).__name__, seconds=round(time.perf_counter()-started, 3))
                results.append(row)
                print(f'Phrase {index+1}: {model}: {row["status"]}', flush=True)
    output = root/'data'/'stt-comparison'/time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    (output/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    def cell(value): return '<td>'+html.escape(str(value or ''))+'</td>'
    rows = ['<tr>'+''.join(cell(row.get(k)) for k in ('sample','model','expected','transcript','language','seconds','status'))+'</tr>' for row in results]
    (output/'compare.html').write_text('<meta charset="utf-8"><title>STT comparison</title><style>body{font:16px system-ui}td,th{padding:12px;border:1px solid #ccc}table{border-collapse:collapse}</style><h1>Same-recording transcription comparison</h1><p>Review missing or changed words, names, numbers and language switches. Seconds measure one network request, not full conversation delay. This is a single-run comparison; repeat before drawing latency conclusions.</p><table><tr><th>Phrase</th><th>Model</th><th>Expected</th><th>Transcript</th><th>Language</th><th>Seconds</th><th>Status</th></tr>'+''.join(rows)+'</table>', encoding='utf-8')
    print(output/'compare.html')


if __name__ == '__main__':
    main()
