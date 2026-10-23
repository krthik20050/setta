# Sarvam comparison run — 2026-10-20

User listening update: candidates **6 and 8** are the user's preferred generated voices; the user reports close resemblance to the desired voice. Both existing voice IDs and source/output mappings are preserved in the private `user-preferences.json`. No single default was selected. Candidate 7 and all outputs remain retained. This is subjective user feedback, not an independent similarity score or a per-language evaluation. The next useful check is longer Malayalam and natural language-switching with these two candidates before choosing the live-agent default.

Result: all three saved candidate voices were created successfully and all nine requested WAV samples were generated. The runner reached `generated_awaiting_human_comparison`. Checksums, 24 kHz WAV format and full FFmpeg decoding passed for every output; details are in the private output folder's `verification.json`. Listening comparison and selection of the winning voice remain pending. No desktop-agent integration was performed.

Runner: `D:\projects codes\PROJECT SETTA\tools\voice\sarvam_compare.py`.

Private output folder: `D:\projects codes\PROJECT SETTA\assets\mother\voice\experiments\sarvam-2026-10-20\` (ignored by Git).

## Scope and authorization

The user confirmed mother's consent, selected references 6/7/8, chose Sarvam and supplied the API key in the root `.env`. Only the three approved WAV excerpts are used. No full-length teaching audio is uploaded by this runner. This run creates three separate saved candidates and generates matching short English, Malayalam and Hindi passages for comparison. No subscription changes or credit purchases are performed.

## Records

- `preflight.json`: sanitized authenticated voice-list check. HTTP 200 was received; the key is not printed or stored here.
- `experiment.json`: source paths and checksums, reference-to-voice-ID mapping, provider-generated reference transcripts, exact test texts, request IDs, generation settings, output hashes/durations, progress and final status. This is the authoritative completion record; preparation alone is not a completed experiment.
- `clip-6-en-IN.wav`, etc.: generated synthetic speech, up to nine WAV files total.
- `listen.html`: comparison page showing each original reference and its generated outputs. Serve the **voice folder**, not just the experiment subfolder, so relative links to original references work.
- `last-error.txt`: sanitized latest failure if any. No API headers or credentials are logged.

Serving command from the project root:

```powershell
python -m http.server 8768 --bind 127.0.0.1 --directory assets/mother/voice
```

Page: `http://127.0.0.1:8768/experiments/sarvam-2026-10-20/listen.html`.

## API behavior

Official REST API at `https://api.sarvam.ai`, key in `api-subscription-key` header. `POST /voices/create` uses multipart reference file, reference language `en-IN`, and conversational style. `POST /voices/clone` uses saved voice ID, exact text, target language, WAV output, 24 kHz and quality control enabled. The service does not expose a specific model version through the parameters used here; none is invented in the experiment record.

The runner checks approved-file hashes before upload, saves voice IDs before generation, and validates returned WAV headers/durations. Billable POST requests have no automatic retries. If voice creation was interrupted, reconcile the provider voice list before another creation attempt. Successful generation is provider output proof, not a family listening assessment or end-to-end desktop-agent integration.

API sources checked at execution time:

- https://docs.sarvam.ai/api-reference/voice-cloning/create-voice
- https://docs.sarvam.ai/api-reference/voice-cloning/clone
- https://docs.sarvam.ai/api/getting-started/pricing

The passages are short conversational tests, not claims about the mother's actual words, memories or beliefs. User should assess identity resemblance, accent/pronunciation, rhythm and artifacts separately and record the chosen reference/voice ID. No winning voice is selected automatically.
