# Voice failure diagnosis and thought-bubble UI — 2026-10-20

## Requested behavior

User requested stopping the companion after a failed speaking attempt, replacing the rectangular text box with a cloud/thought bubble like the attached illustration, and animating the character's face during speech. The recorded SETTA process was verified by its project command line and stopped. **No companion restart or physical microphone/speaker activation was performed during this fix.**

## Evidence and fixes

The prior stderr log contained camera/TensorFlow telemetry warnings, but no recorded voice failure identifying the user's exact failed turn. Initializing the default microphone succeeded. A fixed synthetic question through the actual shared `LiveConversation`/Groq adapter also succeeded. These checks do not establish why that particular user attempt stopped.

Two deterministic regression cases failed before the fix and passed afterward:

1. Explicitly starting Voice Chat left `muted=True`; speech synthesis/playback could be skipped unless the user separately enabled output. Voice Chat now enables spoken replies when explicitly started. Microphone still remains off at application launch. Mute remains available while a session runs.
2. `wave.Error` was not handled by the worker. A malformed returned WAV could kill the thread without a useful UI message. WAV/EOF/config failures now produce a visible stopped-state message with the stage. This is a tested failure path, not an assertion that the user received a malformed WAV.

Failures now record only UTC time, stage and exception type in `runtime/voice-error.json`. Stages distinguish initialization, microphone, recognition, reply, synthesis and playback. No microphone audio, transcript, credentials or raw provider body is written there. Error bubbles persist until replaced by a user action/new message. Regression fixtures use their own temporary diagnostic folder.

## UI and speaking motion

- `src/thought_bubble.py`: irregular smooth cloud outline, cream fill, dark green stroke and two thought dots leading toward the character. Pixel-measured Nirmala UI text pages replace fixed character-count wrapping. Gentle vertical motion is bounded to 1.4 pixels; animation timers are canceled when the bubble is replaced/cleared.
- `src/app.py`: uses the cloud for listening, thinking and response messages. Thinking/listening text and in-progress speech persist while needed; completed replies retain their normal timeout. Text can paginate without deleting words.
- `src/speaking_face.py`: small native-canvas mouth motion on the exact approved resting pose. Body and head stay still, avoiding the older scolding/pointing animation frames. Playback-start callback activates talking; playback completion/stop returns to resting pose.
- This is a simple timed mouth animation during playback, **not phoneme-level lip synchronization** or a regenerated face. A successful Windows playback API call is not independently observed audible receipt.

## Verification

- 54 tests passed, including the two failure regressions, original application tests, bubble geometry/pagination and stable mouth anchor.
- Actual Tk drawing smoke created the cloud/text/dots successfully; text bounding box fit in the reserved bubble area.
- `tools/voice/verify_voice_worker.py --live` exercised the real worker and actual Groq/Sarvam services with prerecorded synthetic input, temporary memory and simulated Windows playback. Observed states: listening, thinking, talk, review, idle. One valid 24 kHz speech chunk was produced, and the session stopped after that turn. Result: `runtime/voice-worker-check.json`.
- Physical live microphone recognition and audible speakers remain unverified. No claim that all provider artifacts/fillers or every possible failure are eliminated.

## Preview artifacts

- `docs/previews/thought-bubble-preview.png`
- `docs/previews/thought-bubble-speaking.gif`
- Reproduce with `python tools/render_companion_preview.py`.

These are offline UI illustrations using the shared cloud geometry and approved artwork, **not desktop screenshots**. The supersampled preview approximates Tk's native smoothing. No private audio or credentials are embedded.

When the user is ready to test again: start with `python setta.py`, then choose Voice Chat/Alt+M. Spoken replies enable with that action; a future failure should show its stage and retain a minimal diagnostic. The application was deliberately left stopped after this request.
