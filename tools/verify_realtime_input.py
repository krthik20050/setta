"""Provider smoke using only the explicitly generated runtime fixture, no microphone."""
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.paths import PROJECT_ROOT
from src.realtime_input import capture_turns
import os


def main():
    load_dotenv(PROJECT_ROOT/'.env')
    fixture = PROJECT_ROOT/'runtime/realtime-synthetic.wav'
    with wave.open(str(fixture)) as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError('Fixture must be 16kHz mono PCM16')
        pcm = wav.readframes(wav.getnframes())
    stopped = threading.Event()
    timer = threading.Timer(25, stopped.set)
    partials = []
    started = time.monotonic()
    class Source:
        def __init__(self):
            self.offset = 0
            self.stream = self
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size):
            time.sleep(size/16000)
            value = pcm[self.offset:self.offset+size*2]
            self.offset += size*2
            return value.ljust(size*2, b'\0')
    result = {'fixture':'synthetic Windows speech; no microphone', 'partials':0, 'committed':False}
    timer.start()
    stream = capture_turns(os.environ['SARVAM_API_KEY'], stopped, lambda:False,
        lambda text:partials.append((time.monotonic()-started, text)), lambda active:None)
    try:
        with patch('src.realtime_input.sr.Microphone', return_value=Source()):
            for captured, turn in stream:
                result.update(committed=True, language=turn.language, text=turn.text,
                    captured_seconds=round(len(captured.frame_data)/32000,3),
                    commit_seconds=round(time.monotonic()-started,3))
                break
    except Exception as error:
        result['error_type'] = type(error).__name__
    finally:
        stopped.set()
        stream.close()
        timer.cancel()
    result['partials'] = len(partials)
    result['first_partial_seconds'] = round(partials[0][0],3) if partials else None
    (PROJECT_ROOT/'runtime/realtime-input-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['committed'] and partials else 1

if __name__ == '__main__':
    raise SystemExit(main())
