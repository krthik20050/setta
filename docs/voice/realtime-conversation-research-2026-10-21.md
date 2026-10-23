# A reliable native voice engine for Amma

Research date: 21 October 2026, Asia/Calcutta. Decision: replace the clip-oriented conversation loop with a native streaming pipeline. Keep the desktop character, approved Sarvam cloned voices, pronunciation rules, Manglish display and local memory. This report is research and a proposed design, not a deployed streaming engine.

## What the local evidence actually shows

The local journal snapshot contained 26 native captures, 7 interrupted native replies, 3 capture-limit events, 3 speaker-overlap rejections and 2 native-turn errors. These are different stages, not disjoint populations or failure rates. The last 20 saved input WAVs were inspected locally for duration and amplitude; none were uploaded. Eight had no 20-ms analysis window above RMS 450, despite entering the conversation workflow. Several of those captures had recorded peak levels below 82; normal voiced recordings in this sample had peaks above 3000. Three WAVs were approximately 27.1–27.2 seconds long.

Evidence: runtime/voice-research-evidence-2026-10-21.json. It contains IDs, stage counts, duration and amplitude statistics, not conversation text. Low energy is not proof of silence: soft speech remains possible. Echo versus user speech cannot be established from amplitude alone. Captures require listening or labelled replay to establish their true content.

Source trace in src/sarvam_voice.py and src/native_capture.py explains mechanisms consistent with the complaints:

| Symptom | Observed implementation | Inference / next proof |
|---|---|---|
| Thinking when nobody speaks | SpeechRecognition can complete a clip without MonitoredStream confirming sustained speech; every accepted clip invalidates the reply epoch and shows thinking before a usable transcript exists. | Low-energy/noise clips can enter reply handling. Replay labelled silence and inspect the exact state transitions. |
| Amma stops mid-answer | A completed microphone clip invokes interrupt(), even without a validated new user transcript. Optional barge-in also uses amplitude onset. | A false capture can cancel valid playback. Correlate capture IDs with output playback intervals and speech labels. |
| Mid-sentence answers | A 2.2-second silence timer determines completion; no semantic completion detector exists. | Longer thinking pauses still look like completed turns. |
| Recording-limit warning | listen(... phrase_time_limit=27), then reject duration >=26.9 seconds. | This is a deliberate local limit for short REST uploads, not evidence that live speech must stop every 27 seconds. |
| Delay or seemingly missed turn | Blocking STT/reply/TTS calls, a single-slot latest-turn queue and cancellation do not stop an HTTP request already executing. | Requests may remain busy while newer audio arrives. Log network and playback stages separately. |
| Wrong stage in an error | Shared _phase may retain playback from a previous turn when recognition fails. | Per-turn stage ownership is needed; the old label is not reliable attribution. |

Earlier fixes improved cancellation and logging, but did not add acoustic echo cancellation, a trained speech detector, streaming input or semantic endpointing. Passing synthetic lifecycle tests does not establish normal conversation quality.

## Chunking: three different operations

1. Send small PCM packets continuously to STT. For example, 100 ms of 16-kHz, 16-bit mono is 3200 bytes. Packets are transport units, not conversational turns.
2. Receive provisional transcript revisions while the user speaks. Replace the current partial display; do not append overlapping hypotheses as new permanent messages. A provider-final segment can still be part of a longer user turn.
3. Commit one complete user turn, then generate one answer. Later, speculative generation can use stable hypotheses, but must remain cancellable and must not execute tools or write durable facts before commit.

Sending every word to a separate answer request would multiply quota usage, duplicate responses and increase interruption races. Streaming is useful because it overlaps work and improves evidence for turn-taking, not because every packet should receive a reply.

## Public implementations worth using

### Sarvam Realtime STT: the most direct input upgrade

The documented `/speech-to-text-realtime/ws` interface provides partial and final transcripts, per-event language, configurable endpointing and structured errors. Its language list includes Malayalam, Hindi and English. The separate API comparison describes continuous chunked audio, whereas REST accepts short clips. This removes the architectural reason for our 27-second user-turn rejection; session reconnect and buffering limits still need handling. [Realtime protocol](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming), [transport comparison](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/which-api-to-use).

Start by testing `saaras:v3-realtime` and `saaras:v4` on the same labelled microphone recordings. Do not assume the newest version is most accurate. Initial settings should use automatic language detection and preserve code mixing. A client turn controller must own the final boundary if provider VAD is only supplying provisional segments.

### Pipecat: recommended orchestration candidate for this desktop

Pipecat has a PyAudio-based local input/output transport and a Sarvam Realtime adapter that converts interim/final events into pipeline frames. This fits a native Python worker without a browser voice page. The current GitHub source also supports manual endpoint ownership and configurable interruption. [Local audio source](https://github.com/pipecat-ai/pipecat/blob/9b0459b47675324843ffea17d90d8d3e422eb92c/src/pipecat/transports/local/audio.py), [Sarvam adapter](https://github.com/pipecat-ai/pipecat/blob/9b0459b47675324843ffea17d90d8d3e422eb92c/src/pipecat/services/sarvam/stt.py).

Use it behind the existing application controller, not as a replacement for Tk, memory or the character. A custom cloned-TTS adapter is required: a stock Sarvam preset-voice example is not sufficient to preserve the mother's saved voice IDs. Package compatibility and interruption behavior must be checked in an isolated environment before integrating.

Version drift is real: Sarvam's production guide describes its Pipecat adapter as restricted to v3-realtime, while inspected Pipecat main accepts v3-realtime and v4. Pin and inspect the actual release selected for the implementation rather than copying mixed-version examples. The guide also highlights reconnect and interruption ownership pitfalls. [Production guide](https://docs.sarvam.ai/api/integration/pipecat-production-guide).

### LiveKit: useful design and evaluation reference

LiveKit separates activity detection, turn completion, interruption and preemptive generation. Its tuning guide includes false-interruption recovery; a noise event need not permanently cancel valid speech. It is a strong alternative if a larger realtime transport deployment becomes useful, but is not required to add streaming to this local Tk app. Some adaptive features have service allowances or costs. [Turn-taking guide](https://docs.livekit.io/agents/logic/turns/tuning/), [adaptive interruption](https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/).

### Semantic completion models: Malayalam is the important gap

Smart Turn operates on audio and publishes a 23-language list including English and Hindi, but not Malayalam. Its CPU model is an evaluation candidate; its published timing is not a laptop measurement. [Smart Turn](https://github.com/pipecat-ai/smart-turn/tree/4786657e242dfe77dd138699ac564ee074a2a543).

LiveKit's currently documented audio detector language list also omits Malayalam. Therefore neither is a verified universal endpoint controller for Amma. Evaluate supported-language modes first; keep Malayalam decisions conservative until a labelled Malayalam/code-mixed dataset establishes performance. [Detector documentation](https://docs.livekit.io/agents/logic/turns/turn-detector/).

Silero is a separate speech-versus-non-speech detector. It does not decide whether an unfinished thought is complete and does not cancel echo. It can replace the current volume-only speech gate as a candidate after replay evaluation. [Silero repository](https://github.com/snakers4/silero-vad).

### Native echo cancellation: a necessary output/input connection

An echo canceller needs both microphone PCM and the exact audio sent to the speakers, with compatible sample rates and timing. Noise suppression alone cannot reliably remove the mother's voice coming from laptop speakers. `pywebrtc-audio` exposes a near/far audio interface and publishes Windows wheels; PyPI lists a CPython 3.13 x64 wheel for 0.2.0, matching this interpreter family. This establishes packaging availability, not usable acoustic performance. [Repository](https://github.com/strands-labs/pywebrtc-audio), [PyPI](https://pypi.org/project/pywebrtc-audio/0.2.0/).

Replace opaque winsound file playback in the streaming engine with a paced PCM output queue. Feed the same rendered PCM into AEC. Speaker buffering, clock drift and resampling must be measured. Headphones remain a useful baseline, not the final product requirement.

### Stream the existing cloned voice

Sarvam's beta `/voices/clone/ws` accepts a saved voice ID and incremental text, returning audio frames and completion events. This is directly relevant to the approved clone rather than Bulbul preset voices. A reconnect/cancel strategy is required, and unsupported parameters from REST must not be copied blindly. [Cloning WebSocket documentation](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/websocket-streaming).

### What we can learn from OpenAI

The public Realtime API distinguishes volume/silence VAD from semantic completion and exposes configurable interruption behavior. Its conversation guide also covers cancellation and synchronization with played audio. These are useful design references, not proof of ChatGPT's private stack. [VAD](https://developers.openai.com/api/docs/guides/realtime-vad), [conversation control](https://developers.openai.com/api/docs/guides/realtime-conversations).

## Recommended end state

```text
Native capture ─→ AEC + noise processing ─→ trained speech gate ─→ Sarvam Realtime STT
                      ↑ speaker reference                         ↓ partial / final segments
Native PCM player ← clone audio queue ← streamed clone TTS ← answer stream ← turn controller
                                                                       ↕
                                                    Groq / tested OmniRoute fallback
                                                                       ↕
                                                   local memory + authorized tools
```

The turn controller distinguishes tentative speech, active user speech, possible end, committed turn, answer generation, speaking and tentative interruption. Only validated nonempty speech should reach a committed turn. Idle/noise must not show thinking or call the reply model. A tentative interruption can pause output; confirmed intentional speech cancels it; a false event resumes the retained output. Track played frames independently of generated text.

Keep partial hypotheses out of durable recall, factual extraction and desktop actions. Archive raw/provider events with correlation IDs for diagnosis. Persist committed user turns once. Persist only completed/heard reply segments in conversational recall; retain the entire generated response in the diagnostic archive with interrupted status. Do not fabricate exact word alignment for partially played audio.

Keep reply fallback separate from audio correctness. Changing Groq to another model does not add AEC or repair turn boundaries. Failover after partial audible output needs special handling to avoid restarting the same answer aloud. Preserve native-script speech text, Manglish display, restrained personality and approved per-language voice routing.

## Recommendation and limits

Build an isolated Pipecat-based native streaming slice using Sarvam Realtime STT, a custom saved-clone adapter, native PCM playback, speech validation and explicit turn ownership. Evaluate native AEC with real render-reference audio. Keep the old engine available during evaluation; choose a new default only after recorded-replay and speaker/headphone trials pass. No new engine or package was installed by this research.

Source revisions recorded: Pipecat `9b0459b47675324843ffea17d90d8d3e422eb92c`; Smart Turn `4786657e242dfe77dd138699ac564ee074a2a543`; LiveKit Agents `40552342d7546e6eac4a959bbe29c7a17d8d63ba`; pywebrtc-audio `1bc860a2051c2b9b3c10b8c778770794b9321d84`. PyPI snapshot: pipecat-ai 1.13.0, Python >=3.11; pywebrtc-audio 0.2.0. Main-branch source and released packages must not be assumed identical. All provider features, costs and compatibility require a live integration check before shipping.
