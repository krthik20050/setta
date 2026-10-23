"""Audio-energy-driven baked character poses, not a painted mouth overlay."""
from dataclasses import dataclass
import io
import math
import wave

import numpy as np


@dataclass(frozen=True)
class SpeechMotion:
    levels: tuple[float, ...]
    step: float
    duration: float

    @classmethod
    def from_wav(cls, audio: bytes, step: float = .05):
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
            raw = wav.readframes(wav.getnframes())
        if width != 2:
            raise ValueError('Speech animation expects 16-bit PCM WAV')
        samples = np.frombuffer(raw, dtype='<i2').astype(np.float32).reshape(-1, channels).mean(axis=1) / 32768
        hop = max(1, round(rate*step))
        rms = [float(np.sqrt(np.mean(samples[i:i+hop]**2))) for i in range(0,len(samples),hop)]
        peak = max(float(np.percentile(rms, 90)) if rms else 0, .008)
        levels = tuple(0.0 if value < .004 else min(1.0,value/peak) for value in rms)
        return cls(levels, step, len(samples)/rate)

    def frame_at(self, elapsed: float) -> int:
        if elapsed < 0 or elapsed >= self.duration or not self.levels:
            return 0
        level = self.levels[min(int(elapsed/self.step),len(self.levels)-1)]
        if level < .12:
            return 0
        # Two conversational hand poses, four integrated mouth shapes per pose.
        # Hand motion is deliberately slower than syllabic mouth motion.
        gesture = 1 if math.sin(elapsed*2.0-.8) > .25 else 0
        mouth = 1 if level < .4 else 2 if level > .72 else 3
        return gesture*4 + mouth
