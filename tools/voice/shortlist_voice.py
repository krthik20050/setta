"""Local-only reference screening. Scores are heuristics, not identity/quality proof."""
from pathlib import Path
import html
import json
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]
VOICE = ROOT / 'assets/mother/voice'
OUT = VOICE / 'shortlist'
RATE = 16000


def decode(path: Path) -> np.ndarray:
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1',
                             '-ar', str(RATE), '-f', 'f32le', '-'],
                            capture_output=True, check=True, timeout=120)
    return np.frombuffer(result.stdout, dtype='<f4').copy()


def metrics(audio: np.ndarray, intervals: list, start: float, end: float) -> dict:
    clip = audio[round(start * RATE):round(end * RATE)]
    frames = clip[:len(clip)//320*320].reshape(-1, 320)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    times = start + (np.arange(len(frames)) + .5)*.02
    speech = np.zeros(len(times), dtype=bool)
    for a, b in intervals:
        speech |= (times >= a) & (times <= b)
    occupied = float(speech.mean())
    db = 20*np.log10(rms + 1e-9)
    dynamic = float(np.percentile(db[speech], 90)-np.percentile(db[speech], 10)) if speech.any() else 99.
    clipped = float(np.mean(np.abs(clip) >= .995))
    peak = float(np.max(np.abs(clip)))
    # Relative quiet-frame contrast is NOT a calibrated SNR estimate.
    contrast = float(np.percentile(db, 75)-np.percentile(db, 10))
    energy = float(20*np.log10(np.sqrt(np.mean(clip**2))+1e-9))
    score = 100 - 70*abs(occupied-.88) - 1.2*max(0,dynamic-14) - min(50,clipped*10000)
    score -= max(0, -32-energy)*2 + max(0,energy+12)
    return dict(score=round(score,2), speech_fraction=round(occupied,3),
                clipping_fraction=round(clipped,6), speech_level_spread_db=round(dynamic,2),
                rms_dbfs=round(energy,2), peak=round(peak,4),
                quiet_frame_contrast_db=round(contrast,2))


def write_wav(path: Path, samples: np.ndarray) -> None:
    samples = resample_poly(samples, 3, 2)
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes((np.clip(samples, -1, 1)*32767).astype('<i2').tobytes())


def render(rows: list) -> None:
    cards = []
    for row in rows:
        transcript = html.escape(row.get('transcript', 'Transcription not run.'))
        cards.append(f'''<article><h2>{row['rank']}. {html.escape(row['id'])}</h2>
<p>{row['start']:.2f}–{row['end']:.2f}s · heuristic score {row['score']} · speech {row['speech_fraction']:.0%}</p>
<audio controls preload="none" src="{row['file']}"></audio><p>{transcript}</p>
<p><a href="https://www.youtube.com/watch?v={row['id']}&t={int(row['start'])}">Source at timestamp</a></p>
<label><input type="checkbox"> Only her voice, no music or interruption</label><br>
<label><input type="checkbox"> Familiar natural delivery; complete phrase</label></article>''')
    page = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Mother voice reference shortlist</title><style>body{font:17px/1.6 system-ui;max-width:850px;margin:40px auto;padding:0 20px;background:#faf9f6;color:#242424}article{padding:22px 0;border-bottom:1px solid #ccc}audio{width:100%}h1{line-height:1.2}label{font-size:15px}</style>
<h1>Voice reference listening shortlist</h1><p>Unfiltered 24 kHz mono PCM WAV clips. Automatic screening only: no claim of speaker identity, absence of music, noise level, or sentence completeness. Scores do not measure clone resemblance. Listen before uploading. Checkboxes are temporary listening notes and are not saved.</p>'''
    (OUT/'listen.html').write_text(page+'\n'.join(cards), encoding='utf-8')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if '--transcribe' in sys.argv:
        from faster_whisper import WhisperModel
        rows = json.loads((OUT/'candidates.json').read_text(encoding='utf-8'))
        model = WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4, local_files_only=True)
        for row in rows:
            segments, info = model.transcribe(str(OUT/row['file']), beam_size=1, vad_filter=False,
                                              condition_on_previous_text=False)
            row['transcript'] = ' '.join(s.text.strip() for s in segments)
            row['detected_language'] = info.language
            row['transcript_status'] = 'Automatic and unverified; not used to establish complete sentences.'
            print(row['rank'], row['transcript'], flush=True)
            (OUT/'candidates.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
        render(rows)
        return
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    manifest = json.loads((VOICE/'manifest.json').read_text(encoding='utf-8-sig'))
    selected = []
    scan = []
    for item in manifest:
        # Prefer original Opus over the MP3 derivative where retained.
        source = VOICE/'originals'/f"{item['id']}.webm"
        if not source.exists():
            source = source.with_suffix('.mp3')
        audio = decode(source)
        vad = get_speech_timestamps(audio, VadOptions(threshold=.65, min_speech_duration_ms=350,
                                  min_silence_duration_ms=180, speech_pad_ms=0))
        spans = [(v['start']/RATE, v['end']/RATE) for v in vad]
        candidates = []
        for i, (a, _) in enumerate(spans):
            if a < 10 or a > len(audio)/RATE - 16:
                continue
            # Start and end at VAD boundaries; these aren't guaranteed sentence boundaries.
            ends = [b for _, b in spans[i:] if 10 <= b-a <= 14.5]
            for b in ends:
                start, end = max(0,a-.12), min(len(audio)/RATE,b+.18)
                values = metrics(audio, spans, start, end)
                if values['speech_fraction'] < .65:
                    continue
                candidates.append(dict(id=item['id'], start=round(start,3), end=round(end,3),
                                       source=str(source.relative_to(ROOT)), **values))
        candidates.sort(key=lambda r:r['score'], reverse=True)
        chosen = []
        for candidate in candidates:
            if all(abs(candidate['start']-c['start']) >= 25 for c in chosen):
                chosen.append(candidate)
            if len(chosen) == 2:
                break
        for row in chosen:
            row['file'] = f"{row['id']}_{row['start']:.2f}.wav"
            write_wav(OUT/row['file'], audio[round(row['start']*RATE):round(row['end']*RATE)])
        selected.extend(chosen)
        scan.append(dict(id=item['id'], duration_seconds=len(audio)/RATE, speech_regions=len(spans),
                         windows_scored=len(candidates), exported=len(chosen)))
        print(item['id'], 'regions',len(spans),'windows',len(candidates),'exported',len(chosen), flush=True)
    selected.sort(key=lambda r:r['score'], reverse=True)
    # Eight-listening-clip set: one per recording, to avoid one recording dominating.
    shortlist = []
    for row in selected:
        if row['id'] not in {r['id'] for r in shortlist}:
            shortlist.append(row)
    for rank, row in enumerate(shortlist,1):
        row['rank'] = rank
    (OUT/'candidates.json').write_text(json.dumps(shortlist,indent=2),encoding='utf-8')
    (OUT/'alternates.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
    (OUT/'scan.json').write_text(json.dumps(scan,indent=2),encoding='utf-8')
    render(shortlist)
    print('Shortlist:', OUT/'listen.html', flush=True)


if __name__ == '__main__':
    main()
