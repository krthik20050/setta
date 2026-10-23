"""Temporal cues, not diagnoses. Thresholds need personal calibration."""


class FaceActivity:
    def __init__(self):
        self.started = None
        self.last_seen = None
        self.last_yawn = float('-inf')
        self.eyes_since = None
        self.summary = 'No face detected'

    def update(self, now, jaw=0.0, eyes=0.0, present=True):
        if not present or (self.last_seen is not None and now - self.last_seen > 0.7):
            self.started = self.eyes_since = None
        self.last_seen = now if present else None
        if not present:
            self.summary = 'No face detected'
            return False
        self.eyes_since = (self.eyes_since if self.eyes_since is not None else now) if eyes > 0.7 else None
        self.summary = 'Eyes closed for several seconds' if self.eyes_since is not None and now - self.eyes_since > 2 else 'Face present'
        if jaw > 0.65:
            if self.started is None:
                self.started = now
        elif jaw < 0.25 and self.started is not None:
            duration = now - self.started
            self.started = None
            if 1.5 <= duration <= 8 and now - self.last_yawn > 20:
                self.last_yawn = now
                self.summary = 'Possible yawn detected'
                return True
        if self.started is not None and now - self.started > 8:
            self.summary = 'Sustained mouth opening; uncertain'
        return False
