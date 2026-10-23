# Hands-free conversation and desktop-agent tools

Updated 2026-10-20. The user requested both interruptible hands-free conversation and desktop actions. This is the first working version of both; it does not claim full ChatGPT parity or unrestricted computer control.

## Starting and stopping

The running companion starts a local control server at `http://127.0.0.1:8770/`, with the microphone off. Right-click Amma and choose **Hands-free Live (browser)**, or open that local address. Press **Start hands-free**, then grant microphone access in the browser. Speak naturally; a pause ends the phrase and sends it for transcription. Speaking again stops queued playback and aborts the previous client turn. **Stop microphone** releases the microphone tracks and clears playback. Use one hands-free tab at a time.

Browser mode uses the current mother character on its own page. The native desktop voice worker is stopped/muted while browser mode is active, so both modes do not speak at once. The browser character uses the same four mouth shapes/two hand poses, with timing based on audio chunks. The native floating character does not mirror browser audio frame-for-frame.

## What is implemented

- `src/handsfree.html`: continuous browser microphone capture after an explicit Start; requested echo cancellation, noise suppression and gain control; local energy-based VAD with short pre-roll; automatic phrase submission; progressive 24 kHz PCM playback; interruption cancellation; Manglish display; Start/Stop recovery. It currently uses the browser ScriptProcessor audio callback, not AudioWorklet. Hardware/browser compatibility needs user testing.
- `src/handsfree_server.py`: loopback-only Python HTTP service, per-process session token, exact Host/Origin validation for state-changing requests, bounded audio/request size, up to three pending turn handlers, serialized conversation turns and cancellation tickets. Secrets stay server-side. No CORS wildcard or remote binding. The server returns NDJSON transcript/reply/audio events.
- `src/sarvam_conversation.py`: cloned voice HTTP streaming with `linear16` PCM, the existing approved voice IDs and pace 1.18. Streaming omits QC/VAD fields unsupported by that endpoint. Native language speech text and shared pronunciation corrections remain. The fixed cached greeting path remains available in the original native mode; browser mode does not automatically greet or open a microphone.
- On cancellation, generation already in flight may finish, but stale audio is discarded and future tool executions check the cancellation signal. Pending unacknowledged assistant messages are removed before the next user turn rather than treating unheard output as heard. The user turn remains. This conservatively discards even a partly heard reply; exact heard-word truncation is not implemented.
- `runtime/handsfree-latency.json`: stage seconds only, without user audio, transcript, credentials or titles. The result measures server readiness, not physical speaker receipt.

This version still transcribes complete short phrases and generates the complete short text reply before streaming audio. It does **not** yet provide streaming STT partial captions, streamed LLM sentence generation, semantic VAD, persistent cloned-voice WebSocket sessions or verified acoustic echo suppression. Browser echo cancellation is requested, not guaranteed on every device. Headphones can improve the first test. A quiet click/noise can still interrupt an energy-based detector; real microphone evaluation is necessary.

## Desktop awareness correction

Previously, the reply saw an executable name alongside old chat messages. It had no timestamped desktop history and could repeat an old assistant guess about a Python script. A regression test reproduced the presence of that stale guess in the outgoing context.

`src/desktop_activity.py` now samples the foreground app and configured window title every two seconds. It skips the companion's own process and stores observed activity in `data/memory/desktop-activity.sqlite`, with a default seven-day retention and 5000-transition limit. Current observations expire after five seconds; historical entries carry first/last-seen UTC timestamps. The context setting `foreground_app=false` disables the background reader on restart; `window_title=false` excludes titles. `desktop_history_days` is bounded from 1 to 30. Old desktop activity cannot be reconstructed before tracking began.

Desktop-activity questions omit old conversation excerpts from the evidence bundle. The prompt distinguishes fresh app/window observations from past activity, and does not treat either as proof of exact screen contents, a source file or the user's intent. An app title can still be ambiguous. This is not screenshot vision or full application accessibility-tree inspection.

## Desktop tools

`src/agent_tools.py` and the Groq reply loop supply four local function tools:

| Tool | Behavior |
| --- | --- |
| `get_desktop_context` | Reads current/recent timestamped app observations and clock context. |
| `find_files` | Finds filenames/globs in configured roots, up to 20 results, 10000 filenames or two seconds. Does not read or upload file contents. |
| `open_app` | Requests Windows to open Notepad, Calculator or File Explorer. Requires an explicit opening request in the current user turn. |
| `open_file` | Opens an existing permitted document/media file inside configured roots. Refuses executable/script types, `.env` data and paths escaping the roots. |

Initial file roots are the project, the user's Documents and Downloads folders. Set `context.file_search_roots` in `config/amma.json` to change them; an empty list disables file access. Local filename/path results and requested app/window context can be sent to Groq so it can answer. The tool layer has no arbitrary shell, file writes, deletion, email sending, payments or general click automation.

Groq receives tool schemas, requests a structured call, and local code validates/executes it. Results return to the model in tool messages. The loop is bounded and deduplicates identical calls within a turn, including language repair. Cancellation prevents subsequent execution. `launch_requested` is explicitly not verified app receipt; the assistant must not claim a verified opening from that status.

Examples: “Which app is active?”, “What was I working on?”, “Find face-correction-v10.md”, “Please open Notepad”. Native voice and typed companion chat also use this tool layer. More apps, selected-file reading and Windows UI Automation are later tools, not implied by a broad system prompt.

## Verification

- Python suite: 96 tests passed after the desktop/voice/tool changes. It covers stale-memory exclusion, durable activity metadata, tool path/action boundaries, duplicate-call suppression, streaming field contract, loopback origin/token checks and cancellation removing an unheard reply.
- `node tools/verify_handsfree_client.mjs`: synthetic DOM/audio checks for WAV encoding, abort/stopping playback and progressive PCM scheduling. These do not prove microphone/hardware behavior.
- Live Groq checks with synthetic Codex metadata correctly named Codex and used the filename tool to find the requested document. No actual desktop launch was performed by these checks.
- Live Sarvam streaming produced nonempty PCM with first chunk around 2.0 seconds in one sample. That excludes transcription, reply generation, browser buffers and physical output. Results and the generated WAV: `assets/mother/voice/experiments/handsfree-agent-2026-10-20/`.
- Real microphone turn-taking, speaker echo, interruption comfort, overall end-to-end latency and subjective cloned-voice pronunciation remain for user evaluation. The microphone is never opened by an automated provider test.

## Research and further work

OpenAI's realtime documentation provides useful interaction patterns: speech-start/stop events, configurable/semantic VAD, interruption cancellation, tracking what audio was actually played and function tools. These are API capabilities, not evidence of ChatGPT's exact internal implementation. Our current pipeline keeps Sarvam for the approved mother voice and Groq for replies, rather than silently replacing her with a stock realtime voice. Sources: https://developers.openai.com/api/docs/guides/realtime-conversations, https://developers.openai.com/api/docs/guides/realtime-vad, https://developers.openai.com/api/docs/guides/realtime-mcp.

Sarvam supports persistent cloned-voice WebSockets and HTTP streaming for saved voices; the latter is implemented here. Next latency work is streaming STT and sentence-by-sentence reply generation into a warm WebSocket connection. Keep a bounded playback queue, cancel it immediately on new speech and evaluate heard-word memory on interruption. Sources: https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/http-streaming and https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/websocket-streaming.

Tool calling follows Groq's local execution contract; action authorization remains local code. Browser audio requests standard echo-cancellation constraints. Sources: https://console.groq.com/docs/tool-use/local-tool-calling and https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation.
