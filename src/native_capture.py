"""PCM speech-onset detection for optional headphone barge-in."""
from array import array
import math
import time


class MonitoredStream:
    def __init__(self, stream, threshold, on_speech, playback_active=lambda: False):
        self.stream, self.threshold, self.on_speech = stream, threshold, on_speech
        self.playback_active = playback_active
        self.speaker_audio_detected = False
        self.frames = 0
        self.peak_rms = 0.0
        self.last_frame_at = None
        self.voiced = 0
        self.triggered = False

    def read(self, size, *args, **kwargs):
        data = self.stream.read(size, *args, **kwargs)
        self.last_frame_at = time.monotonic()
        samples = array('h', data)
        rms = math.sqrt(sum(x*x for x in samples)/max(1, len(samples)))
        self.frames += len(samples)
        self.peak_rms = max(self.peak_rms, rms)
        if rms > self.threshold() and self.playback_active():
            self.speaker_audio_detected = True
        self.voiced = self.voiced+1 if rms > self.threshold() else 0
        if self.voiced >= 3 and not self.triggered:
            self.triggered = True
            self.on_speech()
        return data

    def close(self):
        return self.stream.close()

    def reset(self):
        self.voiced, self.triggered = 0, False
        self.speaker_audio_detected = False
        self.frames, self.peak_rms = 0, 0.0
