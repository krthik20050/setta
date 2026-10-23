# Automatic language-aware voice conversation — 2026-10-20

Current behavior is documented in `docs/companion/latency-memory-awareness-research.md`. The implementation/history below predates persistent SQLite memory, current Groq reply selection, pace 1.18, optional QC and recoverable language switching; those newer details supersede conflicting descriptions below.

Testing controls update: the current shared voice implementation starts with spoken replies muted. Right-click and choose **Enable spoken replies**, then **Voice Chat (Alt+M)** to test audible conversation. The menu toggles to **Mute spoken replies** afterward. The microphone remains off until voice chat is activated. Groq routing and this control passed 48 tests; the updated companion was launched for the user. Provider tests use synthetic inputs, so physical mic/speaker receipt still requires a user test.

Current provider selection: user requested Groq. Root `.env` explicitly sets `REPLY_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL=openai/gpt-oss-20b`. Reply requests go to `https://api.groq.com/openai/v1/chat/completions`, with bounded completion tokens and low reasoning effort for this GPT-OSS model. Sarvam still recognizes speech and synthesizes the chosen cloned voices. Recognized text and bounded recent textual history are sent to Groq; audio/reference WAVs are not sent to Groq by this implementation. No raw provider responses or keys are displayed on failure; no provider fallback happens silently. Four live synthetic-input checks passed with correct language and routing; 47 tests passed. Records are in `assets/mother/voice/experiments/groq-conversation-smoke-2026-10-20/`. Physical microphone/speaker conversation remains a separate user test.

OpenAI reply backend update: root `.env` now includes `OPENAI_API_KEY` (blank for user entry) and `OPENAI_MODEL=gpt-4.1-mini`. When a nonempty OpenAI key is loaded at voice-session creation, reply generation uses `https://api.openai.com/v1/responses`; Sarvam continues speech recognition and cloned synthesis. Only recognized text plus bounded recent text history and instructions are sent to OpenAI, not the microphone WAV or mother reference files. Responses use `store=false`, which does not imply zero provider retention. Separate HTTP clients isolate provider credentials. Existing same-language, brevity and selected-voice rules still apply. An OpenAI failure is shown visibly, without silent provider fallback; with the key blank the tested Sarvam reply route remains available. The standalone text-chat window is not changed by this addition.

Offline regression verification after this change: 42 tests passed, including mocked OpenAI request/response handling and credential isolation. No live OpenAI call has been made; key validity, model access, credits and output quality remain unverified until the user supplies the key and a live check runs. Restart the app/session after editing `.env`. Official API guidance: https://developers.openai.com/api/docs/guides/text .

## User review and selection

User preferred candidate **8 for Malayalam** and **6 for Malayalam–English switching**. They reported unwanted filler/stuck artifacts, especially in mixed-language candidate 8, and concern that shorter output could indicate missing content. Feedback is recorded at:

`D:\projects codes\PROJECT SETTA\assets\mother\voice\experiments\sarvam-extended-2026-10-20\user-review.json`

Different duration alone does not establish omissions. No word-completeness or filler-free guarantee is made; the review is subjective listening evidence. No audio is deleted or automatically edited to conceal artifacts.

## Current implementation

- `src/sarvam_conversation.py`: Sarvam REST STT, language-aware text reply and selected voice synthesis. `POST /speech-to-text` uses `saaras:v3`, `language_code=unknown` and `mode=codemix` so English terms can remain in Latin script alongside Malayalam/Hindi.
- `config/voice.json`: model names and provider voice-ID routing. Pure Malayalam uses reference 8; Malayalam containing Latin-script words uses reference 6. Input code mixing or output code mixing activates this route. English and Hindi provisionally use candidate 6 from the earlier approved pair; no separate English/Hindi winner was claimed by the user.
- `POST /v1/chat/completions` uses `sarvam-105b-conversations`, explicit `reasoning_effort=null`, bounded output and a prompt requesting the detected language, short natural replies and no deliberate fillers/stutters. Initial testing with the general reasoning model exhausted a short token budget and was rejected as incomplete; the conversation-specific model is the tested replacement.
- Language is checked each turn, including changes during a session. Supported interactive languages are Malayalam, English and Hindi. Script evidence assists language selection; ambiguous/null language falls back to the last recognized language (initially Malayalam). Other detected languages produce a visible explanatory error. Script checks reject clearly wrong-language generated replies; this is not a full linguistic classifier.
- Replies are prompted to stay at one or two short sentences. Text is divided into at most 220-character chunks, preferring sentence boundaries. All words are retained; no silent truncation is performed. Incomplete model replies are rejected. Service TTS quality control is enabled, without speed/time-stretch overrides.
- `src/sarvam_voice.py`: microphone -> recognize -> reply -> synthesize/play each chunk sequentially -> listen again. No overlapping speech tasks or shared fixed audio filenames. Microphone is not open while generating or playing replies. This is half-duplex: user interruption during speech is not recognized.
- Stop prevents later playback and purges current Windows sound. A microphone capture can take up to its bounded 15-second phrase limit to return; in-flight HTTP calls can take up to their timeout. The worker cannot be started twice while an old worker finishes. No server-side request cancellation is claimed.
- `src/app.py` selects this route when `SARVAM_API_KEY` is configured, otherwise retaining the prior Gemini voice implementation. No Gemini/OpenRouter key is required for the new route. The text-chat window's existing behavior is unchanged.

The model is instructed to act as a warm companion, not claim to be the actual mother or invent personal memories. Voice cloning supplies voice resemblance, not her personality, memories or private knowledge.

## How to use

The source change requires restarting any older running companion. Exit the old instance from its menu, then run from the project root:

```powershell
python setta.py
```

Or use `tools/start.ps1` for background launch with runtime logs. Right-click the companion and choose **Voice Chat (Alt+M)**. The Alt+M shortcut is available when optional `keyboard` support is installed. Speak Malayalam, Hindi, English, or Malayalam mixed with English; the next turn uses automatic detection. Choose Stop Voice Chat / Alt+M to stop. The application does not automatically enable the microphone at launch.

Microphone recordings are sent to Sarvam only while voice mode is active, and reply text is sent there for generation/synthesis. Normal conversation text/history stays in memory, is bounded to four user/assistant turn pairs, and resets with the voice session. No normal microphone recordings or transcripts are written to the project by this implementation. Temporary generated reply WAVs live under ignored `runtime/voice-temp/` and are removed after playback; a process crash could leave files there. `.env` remains the sole local key source plus shell overrides, and provider error messages do not expose raw bodies or keys.

## Verification and limits

- Regression suite: 31 tests passed, covering auto-language request shape, language switching, mixed/pure routes, short chunk preservation, incomplete/wrong-language rejection, HTTP error sanitization and worker/stop behavior, plus existing application tests.
- `tools/voice/verify_conversation.py --live` exercises real provider STT -> text reply -> cloned speech using existing **synthetic generated audio**, without microphone capture. Records: `assets/mother/voice/experiments/conversation-smoke-2026-10-20/results.json`.
- Successful Malayalam, English and Hindi cases were observed. Mixed-case results and WAV verification are stored in the same output folder. The authoritative final details are `verification.json` when present.
- No physical microphone capture, audible speaker receipt, live user conversation, real-time latency target, or elimination of all synthesis fillers is verified. Network round trips, sentence chunking and synthesis can cause pauses. The implementation reduces avoidable long generations/overlap; it does not prove the provider cannot omit or repeat spoken material.
- Provider failures stop the voice session visibly instead of repeatedly charging retries. Restart voice mode after resolving balance/access/network/microphone problems.

API references checked:

- https://docs.sarvam.ai/api-reference/speech-to-text/transcribe
- https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
- https://docs.sarvam.ai/api-reference/voice-cloning/clone
