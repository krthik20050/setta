# Amma: latency, memory, awareness and voice identity

Updated 2026-10-20. This distinguishes working changes from research and future work. No microphone, real camera image or screen contents were captured for provider verification.

## Working changes

- Language switches: the current turn overrides older languages in memory. Prior assistant replies in other scripts are filtered from direct few-shot history. One wrong-language result receives one corrective generation; a second failure returns a recoverable language error and leaves voice mode listening. Failed attempts never become assistant memories.
- Captions: recognized user speech appears as `You: ...` before reply generation. `Amma: ...` appears for each synthesized chunk at playback handoff; the last exchange stays visible until the next turn. Malayalam display uses Manglish. This is phrase-final transcription, not word-by-word live captions or word-aligned subtitles.
- Delivery: the same approved voice IDs and pace 1.18 remain. The profile requests understated warmth, occasional pet names, practical answers and context-appropriate emotion, without routine praise or counseling. Expressions no longer trigger unsolicited mood-based bubbles by default.
- Microphone endpointing uses a 0.45-second pause threshold and 0.25-second retained silence. Calibration runs once at session start rather than before every utterance. The shorter endpoint may split speech with long pauses; increase it if that happens.
- TTS `enable_qc` defaults false and remains editable in `speech_delivery`. This skips an extra generated-audio transcription/verification pass. It is not EQ, denoising, a voice change or a guarantee against missing/repeated words. The text reply and WAV are still checked locally.
- `runtime/voice-latency.json` records stage seconds for the last completed turn without transcripts, audio, app names or credentials. First-audio timing is readiness/handoff, not proof of physical speaker receipt. It excludes speech capture and end-of-speech detection.

## Fresh computer and camera context

`src/desktop_context.py` supplies current timezone-aware local date/time and the executable name of the foreground Windows app. No file scan, browser history, window/document title or desktop screenshot is taken. Enabled flags are in `config/amma.json` under `context`.

`src/app.py` supplies local visible-face-activity cues with a short expiry. They are observations of behavior, not proof of sadness, concentration, sleep or intent. The reply prompt must ask rather than assert feelings.

For a question containing glasses/specs/spectacles, Manglish kannadi/kannada, or the supported native-language equivalents, the companion can send one fresh face crop to Groq vision. It uses the already-running camera, resizes only if needed, does not save the crop, and does not upload background camera frames. The configured current vision model is `qwen/qwen3.8-27b`; the existing key's model list confirmed access. The vision response is restricted to `present`, `absent` or `unclear`, marked as fallible, and expires. Missing camera/access/network evidence returns unknown. It does not identify a person or infer emotions. The user can disable this with `context.camera_on_request=false`.

This is scoped read-only awareness, not unrestricted computer control or the ability to read the contents of the foreground application. Adding screen understanding should use an explicit snapshot request and visible capture control. File search should have selected folders and source paths. Clicking, sending messages and deleting files should remain separate user-requested actions. A system prompt alone grants none of these abilities.

## Persistent memory

The existing SQLite archive is `data/memory/companion.sqlite`. Conversations survive a restart and the reply gets bounded recent, cross-session and relevant FTS5 excerpts. `config/amma.json` stores the editable identity/preferences separately. These are different from the fresh observation stream.

Explicit saved facts now work through the conversation:

- Say `Remember that I prefer short practical replies.` This stores that user statement as a confirmed note, linked to its originating user message.
- Type `remember: reply_style = concise and practical` to save or replace a named fact.
- Type `forget: reply_style` to remove that named confirmed fact. This does not erase original chat messages; the model is told that distinction. Archive erasure and a memory-management screen remain separate work.

Mood guesses and camera/app observations are not promoted into permanent facts. An assistant's claim cannot be the source of a confirmed user fact. Retrieved material is quoted context, never permission to override the profile or perform computer actions.

For later growth, add user-reviewable episodic summaries and multilingual semantic search alongside the existing lexical search; keep original message provenance. Evaluate retrieval across Manglish, native Malayalam, Hindi and English rather than assuming a search model handles code-switching well. This has not been implemented here.

## Research findings and the next latency step

Sarvam documents that QC adds an extra transcription/verification pass: approximately half a second for single-script text and several seconds for mixed text. Actual single-call timings fluctuate; the live check in this project did not establish a repeatable speedup from disabling QC. Do not advertise a measured gain without repeated matched runs. [Generate Speech](https://docs.sarvam.ai/api-reference/voice-cloning/clone)

The present loop is still half-duplex REST: capture a phrase, transcribe it, generate a complete short reply, synthesize, play. True live user captions require streaming STT; lower time to first speech requires streamed LLM sentences into cloned-voice streaming and progressive PCM playback. Sarvam documents HTTP streaming and persistent WebSockets for the same saved clones. Streaming's field contract differs: `enable_qc`, `enable_vad` and duration bounds are not accepted on the HTTP streaming endpoint. The WinSound file player must be replaced with a bounded streaming audio queue; merely changing the URL would not deliver progressive playback. [HTTP streaming](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/http-streaming), [WebSocket streaming](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/websocket-streaming)

Recommended next implementation: streaming Saaras STT for partial/final transcripts; stream completed reply sentences from Groq; persistent Sarvam clone WebSocket; small bounded PCM playback buffers; cancellation on user speech with echo suppression. Measure median and p95 end-of-speech-to-first-audio on real microphone turns. Do not claim a sub-second conversational target from synthetic text generation timings.

Groq Whisper Turbo is an alternative transcription experiment, not an automatic replacement for Saaras: benchmark Malayalam accuracy and code-switching before switching. [Groq speech-to-text](https://console.groq.com/docs/speech-to-text)

## Preserving her original voice texture

Sarvam says the reference copies delivery as well as identity: pace, energy and emotion. A lecture reference therefore carries lecture prosody. Its guidance recommends a clean, consistent, single-speaker 10-15 second clip in the desired conversational style; more duration is not inherently better. [Reference preparation](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/prepare-reference-audio)

Keep pace 1.18 because the user approved it. Keep the approved reference files and voice IDs unchanged. Compare candidate 8 and candidate 6 on exactly the same casual Malayalam text at the same pace and output format, without adding emotion tags or post-processing. Let the user judge resemblance, clarity, pronunciation and comfort separately. The verification script generates this A/B comparison without changing the default routing. A newly recorded relaxed conversational reference is a better next experiment than progressively stronger prompt instructions. No new reference was trained in this change.

For an objective secondary check, speaker-embedding similarity can flag large identity drift, while ASR round-trips check spoken content. Neither is a substitute for the family's listening judgment; target-language pronunciation and expressive style can move embedding scores. SpeechBrain offers speaker verification APIs, but no speaker-similarity score has been computed here. [Speaker verification](https://speechbrain.readthedocs.io/en/latest/API/speechbrain.inference.speaker.html)

Emotional intelligence is implemented primarily as grounded conversational behavior: recognize what the user actually said, remember explicit preferences, choose a proportionate response, avoid forced affection, and accept corrections. Acoustic emotion is a separate capability and the clone REST endpoint documents no emotion/style field. MediaPipe blendshapes describe facial movement, not a glasses classifier or a reliable measure of inner emotion. [MediaPipe blendshapes](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/drawing_styles/face_landmarker/Blendshapes), [Groq vision](https://console.groq.com/docs/vision)

## Reproducible verification and exact locations

- `tests/test_language_switch.py`: reproduces the reported failure and verifies bounded recovery.
- `tests/test_sarvam_voice.py`: transcript/caption/playback order and continued listening after a language failure.
- `tests/test_companion_context_features.py`: context flags, constrained vision request and durable explicit facts.
- `tools/voice/verify_switch_latency.py`: opt-in paid-provider synthetic language-switch test in an isolated temporary memory database. Outputs: `assets/mother/voice/experiments/language-switch-latency-2026-10-20/results.json` and WAVs. The full reply may exceed one chunk; files contain the first chunk, and the report records the count.
- `runtime/vision-provider-check.json`: a synthetic blank-image provider check, not actual glasses recognition proof.
- Configuration: `config/amma.json`, `config/amma.example.json`; keys remain exclusively in `.env`/process environment and are never included in these reports.
- The actual desktop window must be restarted to load these changes. Microphone activation remains explicit through Voice Chat.
