# Mother voice project: storage, history, and next step

Updated 2026-10-20, Asia/Calcutta. Project root: `D:\projects codes\PROJECT SETTA`.

Latest implementation checkpoint: user selected candidate 8 for pure Malayalam and candidate 6 for Malayalam–English switching. The desktop source now implements automatic-language voice conversation with Sarvam STT/chat/cloned speech; older running instances need a restart. Details and remaining microphone/speaker verification gaps are in `docs/voice/automatic-conversation.md`. Real provider synthetic-input checks passed for Malayalam, English, Hindi and mixed Malayalam/English, with 31 local tests passing. Historical "not integrated" statements below describe earlier checkpoints.

Folder organization update: this document is now under `docs/voice/`. The private root `.env` now exists with blank key entries; `setta.py` loads it automatically, with shell variables taking precedence. No Sarvam credential was supplied during cleanup. Code is in `src/`, voice tools in `tools/voice/`, and the approved audio paths below are unchanged. See `docs/folder-reorganization.md` and the root README for the full map. The earlier no-`.env` statement below describes the pre-cleanup checkpoint.

Sarvam execution update: the user subsequently supplied `SARVAM_API_KEY` through `.env`. Authenticated `GET /voices` returned HTTP 200. The authorized three-reference comparison was started using `tools/voice/sarvam_compare.py`. Current creation/generation results and completion status are recorded in `assets/mother/voice/experiments/sarvam-2026-10-20/experiment.json`; see `docs/voice/sarvam-comparison.md` for storage paths and API details. Earlier statements below that nothing was uploaded describe the previous checkpoint. Do not infer completion from this update alone: use the experiment manifest. The desktop application still uses its existing speech backend.

Follow-up: the first comparison completed with nine valid WAVs, and the user preferred candidates 6 and 8. Their selections and voice IDs are in that experiment's `user-preferences.json`. User authorized the longer Malayalam/mixed-language comparison; its independent records are at `assets/mother/voice/experiments/sarvam-extended-2026-10-20/experiment.json`, with method and exact paths in `docs/voice/sarvam-extended-comparison.md`. No default has been chosen and no desktop speech backend has been changed.

## Current decision

The user explicitly chose listening-page clips **7, 8, and 6** as sounding exactly like their mother. All three are approved references; no preference order is inferred. This later direct selection supersedes any ambiguity in the earlier checkbox review. They are excerpts of authentic source recordings, not generated clones or proof of synthesis quality. Consent for cloning and provider uploads was explicitly confirmed earlier in this conversation.

## Approved files

Folder: `D:\projects codes\PROJECT SETTA\assets\mother\voice\references\approved-2026-10-20\`

| Shortlist number | Filename in approved folder | Source video | Source interval (seconds) | Duration |
| --- | --- | --- | --- | --- |
| 6 | `reference-6-CWL4oxYZU3E_190.76.wav` | https://youtu.be/CWL4oxYZU3E | 190.760–205.492 | 14.732 s |
| 7 | `reference-7-SrHkjCDVaVg_11.59.wav` | https://youtu.be/SrHkjCDVaVg | 11.592–24.852 | 13.260 s |
| 8 | `reference-8-GE-hpzahhXM_226.70.wav` | https://youtu.be/GE-hpzahhXM | 226.696–240.340 | 13.644 s |

These are byte-identical copies of the WAVs the user reviewed. SHA-256 checksums and WAV properties were verified after copying. Each file is mono 24 kHz signed 16-bit PCM, between 10 and 15 seconds. Do not overwrite these reviewed versions when preparing later variants.

`manifest.json` in this approved folder stores absolute file paths, source IDs, source intervals, heuristic measurements, automatic transcripts and their unverified status, format, processing history, user-selection statement, and SHA-256 checksums. `earlier-checkbox-review.json` preserves the earlier browser checkbox snapshot. Neither an automatic transcript nor user approval of the voice proves that each sentence boundary is complete; clip 7's automatic transcript ends mid-thought. Preserve originals and document any later trimming separately.

## Full storage inventory

All paths below are relative to `D:\projects codes\PROJECT SETTA\` unless shown otherwise.

| Path | Contents |
| --- | --- |
| `assets\mother\voice\originals\` | Eight full-length MP3 audio tracks, seven retained source WebM/Opus audio tracks, eight downloaded metadata JSON files. These are audio tracks, not full videos. PgOjbuXh_Cg has no retained WebM because its first extraction removed that intermediate. Metadata can contain temporary media URLs and should remain local. |
| `assets\mother\voice\sources.txt` | All eight original YouTube links. |
| `assets\mother\voice\manifest.json` | Full-track source links, titles, exact durations, MP3 sizes and SHA-256 checksums. Total duration 3574.015478 seconds (59 min 34 sec). |
| `assets\mother\voice\decode-check.json` | Full MP3 decoding results: all eight passed. |
| `assets\mother\voice\downloaded.txt` | yt-dlp completion archive used to resume downloads. |
| `assets\mother\voice\download.log`, `retry.log` | Initial failures and successful retry logs. |
| `assets\mother\voice\shortlist\` | Sixteen candidate WAVs; eight presented to the user; `listen.html`; `candidates.json`; `alternates.json`; `scan.json`; original `user-review.json`. |
| `assets\mother\voice\references\approved-2026-10-20\` | Three user-selected reference WAVs, approved manifest, earlier checkbox review. |
| `tools\voice\shortlist_voice.py` | Reproducible local VAD/heuristic screening, WAV export, optional cached-model transcription, and listening-page generation. |
| `.tools\youtube\` | Project-local yt-dlp 2026.08.19 installation used for successful retries. |
| `docs\voice\mother-voice-references.md` | Original eight links, consent record, download evidence and preparation notes. |
| `docs\voice\mother-voice-research-2026-10-20.md` | Provider/model research, prices at research time, limitations, and primary-source URLs. |
| `docs\voice\mother-voice-shortlist-method.md` | Screening algorithm, scoring limits, prerequisites and rerun commands. |
| `docs\voice\mother-voice-status.md` | This consolidated storage/history/checkpoint document. |

## Processing and verification history

1. Saved all eight user-supplied links; researched hosted and local options. User selected Sarvam and confirmed their mother's consent.
2. Initial network and YouTube bot/403 failures blocked downloads. Updated yt-dlp inside the project and retried with supported embedded/Safari clients. All eight MP3s downloaded. No browser cookies were extracted.
3. Checked MP3 durations with ffprobe, computed checksums, and fully decoded all eight with FFmpeg successfully.
4. Scanned the full recordings locally with Silero VAD. Scored 1909 windows. Exported two separated candidates per source and displayed the best-scoring candidate from each source: eight clips, 108.8 seconds total.
5. Used cached faster-whisper-small locally for automatic unverified transcripts. No audio uploaded for screening/transcription. Scores cover occupancy, level spread and clipping; they do not prove noise absence, music absence, single-speaker identity, or voice resemblance. No dedicated music classifier, diarization, or calibrated SNR measurement ran.
6. User listened and marked checkbox notes. Read those states from the live browser and saved the snapshot; the static HTML itself did not persist checkboxes.
7. User explicitly selected clips 6, 7 and 8. Copied them into the approved folder and verified hashes, duration, channels, bit depth and sample rate.

Reference processing: source decoded to 16 kHz mono for VAD; excerpts resampled to 24 kHz and quantized to 16-bit PCM with numeric range limiting. No denoising or loudness normalization applied. The selected sources have small sample excursions over full scale in float decoding, so the reviewed PCM exports can contain limited peaks. This is recorded rather than hidden; any alternative headroom-adjusted export must get a new filename and be compared separately. Higher export sample rate does not recover details removed during decoding or YouTube compression.

## Privacy and durability

Original media, shortlist derivatives, approved references, logs and `.tools` dependencies are excluded by `.gitignore`. Documentation is outside those ignored folders. Files are saved locally; no off-device backup or Git commit has been created or verified. A second private backup of the whole voice folder is recommended for durability; no external sharing or backup has been performed. Never store API credentials in documentation, manifests, generated pages, or Git.

The local listening page was served at `http://127.0.0.1:8767/listen.html`; that URL depends on the local HTTP server running. The saved files remain on disk when the server stops.

## Next Sarvam step

No Sarvam voice has been created, no sample uploaded, and no speech generated yet. `SARVAM_API_KEY` and `SARVAM_API_SUBSCRIPTION_KEY` were absent from this shell; no project `.env` existed at this checkpoint. This does not establish whether the user has an account or key elsewhere.

1. Obtain account access through https://dashboard.sarvam.ai/ and configure its API subscription key securely (for example, local ignored `.env` as `SARVAM_API_KEY`; do not paste the key into chat).
2. Create three separate saved candidate voices, one per approved WAV, with source language `en-IN` after checking the reference language. Do not concatenate the WAVs: compare them independently.
3. Save each returned voice ID and creation response without credentials in a local experiment manifest, mapped to reference filename and checksum.
4. Generate identical short test texts in `en-IN`, `ml-IN`, and `hi-IN` for each candidate (nine outputs). Store exact texts, voice IDs, model/API parameters, request IDs where available, output paths/checksums, and failures. Use available trial credits first; verify balance and current prices before spending or adding funds.
5. User compares resemblance, pronunciation, pace, and artifacts. Record the chosen voice ID, keep the other references, and only then integrate the chosen TTS into the agent.

Documented API workflow: `POST /voices/create` followed by `POST /voices/clone`; saved voice IDs are provider-scoped. See https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/overview and https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/prepare-reference-audio . Recheck beta schemas and pricing at execution time.
