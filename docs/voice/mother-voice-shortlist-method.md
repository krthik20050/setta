# Local voice reference screening

Run `python tools/voice/shortlist_voice.py` from the project root. Requires the existing local NumPy, SciPy, faster-whisper/ONNX Runtime installation and FFmpeg. No API, network access, or credentials are used. Optional local transcription: `python tools/voice/shortlist_voice.py --transcribe` with an already cached faster-whisper-small model.

The script decodes the retained YouTube Opus source where available (MP3 fallback), runs Silero voice activity detection at 16 kHz, and enumerates 10–15 second windows bounded by detected speech regions. It skips the first 10 seconds and requires at least 65% detected speech. It ranks candidates using clipping, speech occupancy, level spread, and overall level. The quiet-frame contrast statistic is descriptive and is NOT a signal-to-noise ratio. Speech detection cannot prove the speaker is the mother or exclude background music, echo, or overlapping speakers. No speaker diarization or dedicated music/noise classifier is run.

Two separated candidates per recording are exported to unfiltered 24 kHz mono 16-bit PCM WAV. The listening page presents the highest-ranked candidate per recording (eight total). This diversity constraint is deliberate; it is not a ranking of the eight globally best windows. Alternates are recorded separately.

Output: `assets/mother/voice/shortlist/listen.html`, `candidates.json`, `alternates.json`, and `scan.json`. Waveforms and transcripts are private local derivatives, ignored by Git. Any transcripts are automatic, unverified, and do not establish complete sentences. VAD boundaries can occur mid-sentence; listen and adjust cuts before upload. No denoising or volume normalization is applied, and original recordings are unchanged.

Before selecting the reference, listen for a complete natural phrase, a single speaker, low noise and echo, absence of music, and familiar delivery. Then compare the best three references by generating the same new texts through Sarvam. Technical screening scores do not establish voice-clone resemblance. No Sarvam upload or generation is performed by this script.
