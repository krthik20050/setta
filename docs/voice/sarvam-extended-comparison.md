# Longer Malayalam and mixed-language comparison — 2026-10-20

Review completed: user chose candidate 8 for Malayalam and candidate 6 for Malayalam–English switching, noting filler/stuck artifacts in some outputs and concern about duration differences. Saved in this experiment folder's `user-review.json`. Application routing now reflects those choices in `config/voice.json`; see `docs/voice/automatic-conversation.md` for implementation and verification. Shorter duration was not treated as confirmed omitted speech.

Completed: all four requested samples generated, 153.99 seconds total. Durations: candidate 6 Malayalam 42.14 s, candidate 6 mixed 43.50 s, candidate 8 Malayalam 33.22 s, candidate 8 mixed 35.14 s (rounded). All four passed SHA-256 verification, 24 kHz WAV checks and full FFmpeg decoding. Original reference checksums remain unchanged; the listening page has six audio players (two originals plus four generated clips), and feedback JavaScript passed syntax checking. User listening review remains pending. These checks do not establish pronunciation correctness or speaker similarity.

Authorized by the user's "Yes, let's do it" after preferring the generated candidates 6 and 8 and proposing longer Malayalam and natural language-switching tests. This experiment reuses their two existing saved Sarvam voice IDs. No additional voice is created, no subscription is changed, and no credits are purchased.

## Exact storage paths

- Runner: `D:\projects codes\PROJECT SETTA\tools\voice\sarvam_extended_compare.py`
- Private outputs: `D:\projects codes\PROJECT SETTA\assets\mother\voice\experiments\sarvam-extended-2026-10-20\`
- Experiment manifest: output folder's `experiment.json`; records both existing voice IDs, source reference checksums, exact Unicode texts, language code, settings, request IDs, output durations/checksums and completion status.
- Outputs: `candidate-6-malayalam.wav`, `candidate-6-mixed.wav`, `candidate-8-malayalam.wav`, `candidate-8-mixed.wav`.
- Listening page: output folder's `listen.html`.
- Output verification: `verification.json` when verification is complete.
- If a request fails, sanitized `last-error.txt` records the failure; a pending request is preserved for reconciliation rather than blindly retried.

The audio and manifests are private local experiment files excluded from Git. API keys are loaded from the root `.env`/shell and never included in these records.

## Test design

Each voice speaks the same two passages, producing four outputs total:

1. A longer Malayalam passage about studying at a comfortable pace, asking questions, taking a break, and explaining lessons in one's own words.
2. A teaching passage switching between Malayalam and English to explain singular/plural subject–verb agreement.

These are newly written test passages, not statements or memories attributed to the mother. The text length is bounded to 1000 characters per request and 2000 across the experiment. Both requests use dominant language `ml-IN`, 24 kHz WAV output and service quality control enabled. No speech-speed or time-stretch override is applied. No new audio reference upload is needed: saved voice IDs are reused.

No voice winner is chosen automatically. Listen for identity/timbre, Malayalam pronunciation, English transitions, pacing, artifacts and drift near the end. Service quality control and valid audio decoding do not establish voice resemblance or perfect pronunciation.

## Listening and recording feedback

The existing voice-folder HTTP server serves this page at:

`http://127.0.0.1:8768/experiments/sarvam-extended-2026-10-20/listen.html`

Start it again if needed:

```powershell
python -m http.server 8768 --bind 127.0.0.1 --directory assets/mother/voice
```

The page pairs candidates 6 and 8 for each passage and includes the authentic original references. Malayalam and mixed-language preference fields plus comments save to this browser's localStorage under `setta-sarvam-extended-20261020`. They are **not** automatically written to the project. The review download button exports a JSON copy, or the user can give feedback in chat for a project record. No feedback is submitted to a third party. No default voice or desktop-agent integration is selected by this experiment.
