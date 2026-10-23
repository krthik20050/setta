# Desktop voice companion research — 2026-10-20

## Product direction
Setta should become a voice-first Windows companion embodied by the approved mother character: continuous conversation, relevant contextual awareness, remembered goals/preferences, caring timing and tone, and explicit desktop actions. Expressive animation is presentation; apparent emotional intelligence must be grounded in conversation and context, not confident mind-reading from webcam expressions.

## Evidence boundary
This survey checked current primary repositories and official documentation, with GitHub metadata for the six core projects. No candidate was installed, benchmarked, or operated on this laptop. Capability descriptions below are project-documented, not independent runtime validation. No application changes or audio unmuting were performed during this research.

## Closest projects

### Open-LLM-VTuber — closest overall interaction reference
Documents hands-free speech, interruption, camera/screenshot perception, desktop pet mode, and mapping backend emotion labels to Live2D expressions. Study its conversation lifecycle, cancellation and expression events. Screen perception is not evidence of unrestricted desktop control. Code and Live2D sample assets have different licensing terms; our mother artwork does not need its sample avatars.
https://github.com/Open-LLM-VTuber/Open-LLM-VTuber

### Mana — closest Windows-specific reference
Documents a Windows-native launcher, local transcription/LLM/TTS, memory, screen text awareness, and interruption by speech or hotkey. Current supported path is its native launcher plus Node backend, not its retired Electron launcher. Study wake/listen state and cancellation, OCR scheduling and local memory. Requires a separate local model stack and .NET 10; on-device capability does not establish acceptable speed on this laptop. GitHub reports Apache-2.0.
https://github.com/Yuuzulight/Mana

### Project AIRI — strongest embodiment reference
Documents realtime voice, Live2D/VRM animation, Windows/macOS/web clients and game integrations. Memory and some game capabilities remain work in progress. Study avatar events, lip motion, gaze/blink/idle behaviour and voice-provider boundaries. Do not equate game integration or existence of a computer-use service with reliable unrestricted desktop operation. GitHub reports MIT.
https://github.com/moeru-ai/airi

### UI-TARS Desktop / Agent TARS — strongest action-layer reference
UI-TARS provides local/remote computer and browser operators driven by visual models. Agent TARS adds a multimodal agent stack with DOM/GUI browser strategies and MCP tools. Useful for observe -> act -> verify loops, task cancellation and tool traces; not a mother-like voice companion by itself. Local UI does not mean model inference is automatically local/free. GitHub reports Apache-2.0.
https://github.com/bytedance/UI-TARS-desktop

### Leon — assistant orchestration reference
Current develop branch is a 2.0 Developer Preview around tools, memory, context and agentic execution; old docs largely describe legacy architecture. Study tool/skill boundaries and memory handling. Use its current core architecture documents, not old tutorials, to assess reuse. GitHub reports MIT.
https://github.com/leon-ai/leon

### Pipecat — recommended voice framework to prototype
A voice/multimodal framework rather than a desktop companion. Supports speech lifecycle, turn handling, interruptions, model/tool pipelines and provider integration. Sarvam publishes integration and production guidance. Study or reuse it for the voice layer while keeping the existing desktop avatar. Confirm Windows microphone/device support and provider latency in a small prototype before adoption. GitHub reports BSD-2-Clause.
https://github.com/pipecat-ai/pipecat
https://docs.sarvam.ai/api/integration/pipecat-production-guide

### LiveKit Agents — voice framework alternative
Official quickstart supports STT/LLM/TTS or realtime-model agents and terminal/browser/telephone/native-app interaction. Good alternative if remote sessions or cross-device media become central. Evaluate operational complexity versus a primarily single-laptop app. Choose one voice framework initially rather than combining both.
https://docs.livekit.io/agents/start/voice-ai/

### Screenpipe — optional context-memory reference
Its current site describes it as source-available, not simply permissive open source. It captures desktop screen/audio for searchable history. Study timestamped retrieval, exclusions and local context storage; avoid adopting continuous recording as a default merely because it exists. Licensing and resource use need separate review.
https://screenpipe.com/about

### Cua and Open Interpreter — computer-use references
Cua supplies drivers/sandboxes/evaluation infrastructure across OSes; this is not a conversational character. Open Interpreter's current repository differs from older OS-mode articles and now describes coding-agent and QA/computer-use workflows. Treat legacy examples cautiously and evaluate the specific current component required.
https://github.com/trycua/cua
https://github.com/openinterpreter/openinterpreter

## Recommended Setta architecture
1. Keep the current avatar/transparent bubble frontend and approved identity assets. Send typed state events to it rather than allowing model text to manipulate animation code.
2. Prototype Pipecat with Sarvam STT/TTS, swappable dialogue model, push-to-talk first and continuous voice later. Implement echo handling, end-of-turn detection, user interruption, cancellation and persistent mute before unsolicited speech.
3. Build a separate context service: foreground app, permitted browser title/domain, idle time, camera identity/quality and temporal facial observations. Attach timestamps, source and uncertainty. No raw continuous webcam stream needs to reach the conversation model.
4. Dialogue model handles open-ended conversation and personality. Laya optionally selects fixed actions such as quiet/check-in/help; it does not provide dialogue, face recognition or emotion understanding.
5. Memory stores user-confirmed preferences/goals and limited useful summaries, supports correction/deletion, and distinguishes user statements from model guesses. Context recall should not invent shared memories or claim the avatar is the real mother.
6. Desktop controller exposes a small explicit tool list. Prefer structured APIs/accessibility/browser DOM where available, then screenshot-guided control when needed. Verify each outcome; model confidence alone is not completion.
7. Keep observe and act permissions separate. Opening an app can be direct when requested; sending messages, deleting files, purchases and account changes need action-specific authorization. A single stop hotkey must cancel speech and pending desktop actions.

## What mother-like emotional intelligence means in the product
Remember the user's current task and preferred language; recognise explicit frustration or requests for encouragement; adapt warmth/strictness within user preferences; ask when cues are ambiguous; stay quiet while the user is working; apologise briefly after an incorrect inference and accept correction. Facial cues are observations, not reliable proof of feelings, honesty or productivity. Avoid escalating nagging simply because the user is silent.

## Build order and acceptance checks
A. Reliable conversation: 20 multi-turn exchanges, successful interruption and stop/mute, no self-transcription loop, measured end-of-speech to first-audio latency.
B. Grounded context: answer what app is active, distinguish a tutorial from leisure using task context, unknown when observations are unavailable, no interruption from Setta's own window gaining focus.
C. Small action set: open apps, switch windows, find local files, set timers, operate one browser workflow. Verify outcomes and recover from denied permissions or changed UI.
D. Memory/personality: remember and correct preferences; distinguish uncertain observations from facts; test quiet mode and caring responses without compulsory scolding.
E. Facial pipeline: guided multi-view enrollment, calibrated matching, track expiry, labelled yawn/talk/laugh clips and false-alarm rates. See side-eye-source-audit.md for details.

## Recommendation
Build a targeted hybrid rather than replacing Setta wholesale: current avatar + Pipecat/Sarvam conversation + local contextual memory + goal-aware policy + bounded Windows action tools. Use Open-LLM-VTuber/Mana as interaction references, AIRI for embodiment, and TARS/Cua for task-execution patterns. This combination is an architectural recommendation; compatibility and performance still need a working prototype.
