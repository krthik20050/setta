# Native realtime voice implementation and acceptance plan

Companion report: realtime-conversation-research-2026-10-21.md. This is a build specification, not completed implementation or a promise of ChatGPT parity.

## Slice 1: continuous audio and visible transcription

Create a native voice-engine adapter behind the existing SarvamVoiceAgent callbacks. Keep Tk updates on root.after and audio/network work on a dedicated asyncio worker. Pin an independently tested Pipecat release in a separate environment first; inspect its native dependencies on Windows/Python 3.13. Do not upgrade the working application's full dependency set blindly.

Open microphone/output devices once. Use bounded queues and explicitly report overflow. Audio callbacks only move PCM buffers; no database writes, model calls or disk operations in callbacks. A separate journal worker records session/turn IDs, packet sequence, dropped frames and capture timestamps. Account for capture, render and provider clocks separately.

Send approximately 100-ms raw PCM packets over Sarvam's Realtime socket, preserving provider event IDs. Display partial hypotheses in the existing native bubble with a listening state. A revision replaces its provisional text. Do not start a reply merely because a partial or provider-final segment arrived. Test server VAD as one initial source of segmentation; disable it in favor of manual endpointing when the controller owns semantic completion. Never let two independent systems commit the same turn.

A continuous 60–90-second utterance must not fail at 27 seconds. Maintain bounded segment buffers and record audio incrementally; reconnect sessions deliberately when provider limits require it. Preserve ordering and mark uncertain gaps after disconnect. Do not silently concatenate lost intervals or replay speech into the LLM twice. Device errors and stopped sockets must visibly leave listening state.

## Slice 2: native acoustic front end

Evaluate pywebrtc-audio against a known render-reference fixture before using it live. Candidate common processing rate: 48 kHz for capture/render and AEC, resampled to 16 kHz for STT. Resample the clone's actual output into the render rate; reference the exact samples placed in the output buffer. Device support determines final rates. Do not degrade the approved voice unnecessarily or assume AEC works with mismatched clocks.

Compare quiet room, laptop speakers, headphones, typing, fan noise and moderate background speech. Train/tune the speech gate separately from endpointing. Reject noise hypotheses before answer generation, but retain their diagnostic events. A high fixed RMS cutoff is not an acceptable substitute for a speech model: it would lose quiet valid speech.

## Slice 3: committed turns and natural interruption

Use states OFF, CONNECTING, LISTENING, USER_SPEAKING, POSSIBLE_END, THINKING, SPEAKING, POSSIBLE_INTERRUPTION and RECOVERING. Define legal transitions and their owner. Transition to THINKING only after one validated turn commit. The UI must not imply ready-to-listen when its input socket has failed.

For supported languages, evaluate Smart Turn and compare it with provider endpointing. For Malayalam/code mixing, require labelled replay before model-controlled endpoint decisions. Start with a conservative fallback and a native Finish speaking/hold-to-talk override, clearly described as such. A future Malayalam endpoint classifier is a separate evaluated component; it is not delivered by downloading an English/Hindi-capable model.

Use generation IDs across ASR hypotheses, LLM output, tools, clone requests and playback buffers. Late frames from old generations cannot play. Distinguish an intentional interruption from cough/noise or short acknowledgment. Consider pausing playback first, confirming speech from partials, and resuming buffered speech on false positives. Do not automatically discard an audible response on a bare volume event.

Only committed user turns may execute desktop tools or promote facts to persistent memory. If the user resumes before audio output, cancel or revise pending answer generation without adding another assistant message. If audio was partially played, retain the known heard prefix and mark any incomplete segment uncertain; generated-but-unheard words remain diagnostic-only.

## Slice 4: streaming replies and saved-clone audio

Use streamed reply tokens through a provider adapter that preserves tool-call events. Begin with one LLM call per committed turn. Do not enable speculative tool execution. On speculative cancellation, ignore all old provider output even if the network call cannot be stopped immediately.

Buffer coherent short clauses/sentences before sending text to the clone socket; word-by-word synthesis can harm pronunciation and prosody. Preserve pace 1.18 and existing pronunciation corrections. Keep pure Malayalam/reference 8 and mixed-language/reference 6 behavior. Choose a stable voice/language before speaking a segment; do not change clone identity on an unstable partial language guess. Reuse compatible per-voice sockets or reconnect cleanly when configuration changes.

Custom clone adapter: configure saved voice_id, receive PCM/audio events, flush utterances, handle final/error/disconnect, and discard cancelled output. The ordinary preset Bulbul TTS adapter must not replace the mother's clone. Stream audio into a native PCM player with a cancellable queue and a measurable render position. Preserve the existing RMS-driven face animation from played audio, not merely queued frames.

Apply Groq/OmniRoute fallback before audible output where possible. If an upstream fails after speech begins, preserve what was heard and recover explicitly; do not silently replay a different full answer from its beginning. Keep keys server-side/local .env and retain existing local memory.

## Reproducible test set

Record each scenario once and replay the exact capture/render streams through candidate versions. Include expected utterance boundaries and human interruption labels, not only expected words. Use the user's actual Malayalam, English, Hindi and mixed speech, plus silence/noise fixtures. Manglish display text and native-script STT need script-aware human scoring; plain WER across different scripts is misleading.

| Scenario | Required outcome |
|---|---|
| Two minutes of silence and fan noise | No committed user turn, answer request or unsolicited thinking state |
| Laundry sentence with 0.5/1/2/3-second internal pauses | No answer before labelled completion; patient mode/override behavior documented |
| 60–90 seconds of continuous speech | Ordered partials and a complete turn; no local 27-second rejection |
| Normal answer through laptop speakers | No self-transcription loop or false cancellation |
| Real interruption while Amma speaks | Output yields promptly; old audio does not restart later |
| Cough, keyboard click, short acknowledgment | No permanent false interruption; resume retained output where appropriate |
| Malayalam-to-English and Hindi switching | Stable language selection, approved voice and correct display rules |
| Deliberately revised partial transcript | One committed user message; no duplicated hypothesis text |
| Socket drop or provider 429 | Visible recovery, no frozen listening state, ordered retry policy |
| Stop and restart Voice Chat | One mic owner and one output owner; no old-generation playback |
| Desktop action followed by interruption | No replay of a completed side effect |
| New chat / app restart | Confirmed name/facts persist; unheard answer is not asserted as a past event |

Proposed engineering targets, not measured promises: zero phantom replies in the two-minute silence fixture; zero lost words attributable to packet boundaries in the long-turn fixture; p95 output stop within 300 ms of a confirmed interruption; p95 first partial within 700 ms of clear speech; p95 first audible reply within 2 seconds of committed end-of-turn under a healthy provider. Measure on this laptop with camera/animation enabled. Report accuracy and delay together; a model can appear faster by cutting users off.

## Evidence and rollout

For every trial, store app/dependency versions, provider/model, device/sample rate, packet/drop counters, VAD probabilities, hypothesis revisions, endpoint scores, commit/cancel reason, request IDs without credentials, generation IDs, first audio and played sample counts. Distinguish capture-to-partial, true-end-to-commit and commit-to-audio timings. Do not subtract an excessive endpoint delay from the claimed user experience.

Keep complete diagnostic recordings local while voice is explicitly active. At 16-kHz mono PCM16, continuously saved raw input alone is about 115 MB/hour; render-reference audio adds storage. Rotate files into bounded chunks without deleting the logical conversation. Keep generated audio, played status and durable memory separate. No 24/7 microphone recording or new cloud memory service is part of this plan.

Promote the engine only after replay tests, provider-contract tests and a live speaker/headphone session pass. Preserve a rollback setting and the existing artwork/configuration. Research compatibility, synthetic tests and hardware acceptance are separate evidence levels. First deliverable: native continuous STT with provisional bubble text, no browser and no 27-second turn rejection. Second: validated speech/endpoint/interruption controller. Third: streamed clone output with AEC reference. Fourth: measured refinement rather than repeated global threshold changes.
