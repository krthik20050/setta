# Native conversation investigation

## Observed evidence

Source inspection found a speaker-safe gate rejecting a complete microphone recording when reply work was busy at the start OR end of listening. Reply work includes STT, reasoning and synthesis, not just audible playback. Consequently a recording could be rejected even if playback had already ended before user speech. The old rejected recordings did not reach the journal, so existing archived turns cannot establish how often this happened on the user's hardware.

The pre-change local journal contained 5 transcription events, 1 transcription error, 6 generated replies and 5 native-playback-finished markers. These counts do not prove complete microphone coverage or identify the missing words. Latest saved completed-turn timings were approximately .672 seconds recognition, .908 reply, 1.953 synthesis, and 3.533 first audio after capture. They exclude speech and endpointing and are one previous sample, not a current performance benchmark.

## Changes

- MonitoredStream records actual loud input overlapping the playback flag; background reply work alone no longer rejects recordings. Without AEC we cannot determine whether overlapping input is echo or the user, so speaker-safe rejections explicitly ask for repetition and preserve the captured WAV.
- Captures are archived before filtering/queue replacement. Journal records capture duration, peak RMS, configured pause, overlap, end reason and supersession. Input/transcription/reply/speech failures remain distinguishable.
- Native pause allowance is 2.2 seconds. This is still silence endpointing, not a semantic classifier. The 27-second REST capture limit remains.
- A monotonically changing turn epoch prevents an old reply from becoming valid when a shared cancellation event is cleared for another turn. In-flight HTTP calls remain synchronous and cannot be force-cancelled by this mechanism.
- Reply-worker fatal errors stop the session visibly instead of leaving a microphone UI with a dead reply worker.
- runtime/native-voice-status.json contains a timestamped heartbeat while native voice is active: latest audio-frame age, RMS, busy/playback/speech flags, queue depth and worker liveness. Treat an old timestamp as stale. No transcripts or credentials are included.

## Memory and location

Existing local SQLite memory remains the source of truth: data/memory/companion.sqlite. Personality stays in config/amma.json; complete diagnostic archive stays in data/conversation-archive. The model now has read-only search_conversation_memory for older conversations, with role and date attached. Retrieved assistant statements are quoted history, not verified facts. Prompt retrieval keeps the top three relevant matches rather than the last three low-ranked matches.

Direct whole-turn self-reports such as "My name is Test Person" and "I live in Test City" save sourced user_name/home_location facts, surviving a new session. Third-person/quoted/hypothetical claims and "Call me tomorrow" do not become identity facts. Core identity/home facts are prioritized within the bounded prompt fact list. A self-reported home city is not live GPS; no OS location access or IP geolocation was added.

## Public designs studied

OpenAI documents server VAD (silence/volume) and semantic VAD (a classifier estimating completion from speech), including lower eagerness to allow longer turns and explicit interruption controls. This is public Realtime API behavior, not evidence of ChatGPT's private implementation: https://developers.openai.com/api/docs/guides/realtime-vad

Hermes documents bounded curated user/agent memory alongside searchable full session history. We adopt that separation while preserving the current SQLite implementation rather than installing Hermes or uploading the archive: https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md

REA routing: this is available source, so normal source tracing and synthetic execution were used. No binary decompilation or inspection of ChatGPT's private internals occurred.

## Remaining validation and next architecture

Regression cases cover playback overlap versus background reply work, cancellation-event races, persistent identity/home facts across a reopened database and source-labelled cross-session search. Synthetic tests cannot establish microphone quality, room echo or natural pause behavior.

Hardware trial: activate native Voice Chat, say the laundry sentence with an internal pause, let Amma finish, then speak immediately. If it fails, inspect the timestamped status and journal/WAV for that exact turn; distinguish missing captured audio, incomplete transcript, provider failure, cancellation and playback failure. Repeat with headphones for automatic interruption. Do not tune five parameters at once.

The next major conversation layer is streamed ASR with provisional transcripts, multilingual turn-completion assessment, real echo cancellation and cancellable output delivery. None of those are claimed by changing a silence threshold. Keep the approved Sarvam cloned voice until a measured replacement preserves its likeness and pronunciation.
