# PROJECT SETTA — Agent Handoff

**Updated:** 2026-10-22  
**Workspace:** `D:\projects codes\PROJECT SETTA`  
**App entry point:** `setta.py`  
**Purpose:** Give a fresh coding agent enough verified context to continue without treating old plans or chat summaries as proof.

## Start here

1. Read this file, then the root `README.md` and the task-specific docs linked below.
2. Inspect the live source and current runtime state before changing anything. This workspace did not expose a Git repository during this handoff (`git status` returned “not a git repository”), so there is no verified branch or diff to rely on.
3. Preserve the user's established product boundaries: this is a private Windows desktop companion called Amma, using the mother's consented cloned voice; displayed Malayalam should be Manglish; don't expose credentials or private face/audio data.
4. Make a small, reviewable change, add comments only where intent is non-obvious, and report exactly which checks ran and what they prove.

## Product and architecture map

PROJECT SETTA is a Windows desktop companion built with Python/Tkinter and CustomTkinter. `src/app.py` coordinates the native UI, character, camera and voice controller. `src/modern_hub.py` contains the Home, Conversation, Reminders, Camera, Connections, Profile/Memory and Settings pages. `src/live_conversation.py` is the shared adapter for typed and spoken turns; `src/sarvam_conversation.py` handles speech recognition, reply providers and cloned-voice synthesis. Local memory is in SQLite. Sarvam owns speech recognition and cloned speech; Groq is the configured reply provider, with a separately configured fallback path.

Typical spoken path: microphone capture → Sarvam recognition/language detection → `LiveConversation` route and context → local action or reply model → Sarvam cloned speech → UI bubble/audio. Conversation transcripts and audio event records are stored locally. Do not assume that a generated reply was heard, or that browser hands-free mode is native desktop mode.

| Area | Main files | Further reading |
|---|---|---|
| Entry, UI and lifecycle | `setta.py`, `src/app.py`, `src/modern_hub.py` | `docs/modern-app-delivery-2026-10-21.md` |
| Voice and turn flow | `src/sarvam_conversation.py`, `src/live_conversation.py`, `src/voice_controller.py` | `docs/voice/automatic-conversation.md`, `docs/voice/native-realtime-input-2026-10-21.md` |
| Local routing/actions | `src/decision_router.py`, `src/local_actions.py`, `src/agent_tools.py` | `docs/companion/decision-routing.md`, `docs/desktop-agent-integration-plan-2026-10-21.md` |
| Memory and profile | `src/companion_memory.py`, `src/companion_context.py`, `src/character_profile.py` | `docs/conversation-memory-contract.md`, `docs/companion/profile-memory-local-actions-2026-10-21.md`, `docs/companion/amma-profile.md` |
| Face enrollment/matching | `src/face_id.py`, `src/webcam.py`, camera coordination in `src/app.py` | `docs/real-people-discovery-2026-10-22.md`, `docs/people-portrait-gallery-2026-10-22.md` |
| Settings and permissions | `config/amma.json` (private), `config/amma.example.json`, `src/modern_hub.py`, `src/character_profile.py` | `docs/companion-settings-2026-10-21.md` |
| API fallback and limits | `src/reply_fallback.py`, `src/reply_errors.py` | `docs/companion/omniroute-fallback.md`, `docs/companion/groq-rate-limit-2026-10-21.md` |
| Local records | `data/memory/companion.sqlite`, `data/conversation-archive/events.sqlite`, `runtime/` | `docs/chat-history-camera-reminders-2026-10-21.md` |

`README.md` has the run instructions and a broader directory map. Tests are under `tests/`; optional audio tools are under `tools/voice/`.

## Decisions and constraints to preserve

- Keep the mother's voice independent from the reply model. Preserve the approved clone IDs/configuration unless the user explicitly asks to change them.
- Keep personal face embeddings, enrolled photos, conversation records and API credentials local. Do not place secrets or sensitive media in handoffs, logs or source control.
- A face match is a tentative local match against enrolled samples, not proof of identity. Unknown/ambiguous results must remain unknown; do not silently enroll or promote a match.
- Camera, desktop, microphone and memory access follow the user's saved Profile/Settings permissions. Actions with external or desktop effects require an explicit request and the existing action gate.
- Memory should preserve provenance and support inspection/correction/deletion. A casual sentence or quoted request is not automatically a durable fact.
- Manglish display and the language used for speech synthesis are separate choices. Never put Malayalam script into the user-facing bubble; native Malayalam may still be needed internally for pronunciation.
- Treat existing design and interaction work as active product behavior. Inspect before editing `src/modern_hub.py` or broad UI/controller files; concurrent prior work has touched them substantially.

## Current identity-question work

The user wants questions such as “Who am I?”, “Who is this?”, “Can you see me?”, and corresponding Malayalam/Manglish and Hindi variants to trigger camera-based checking against saved people.

Current source includes identity phrase routing in `src/decision_router.py` (`asks_who_is_visible`) and an identity branch in `src/live_conversation.py`. The branch checks the camera permission, reads existing `visible_person_label` observations when available, requests the camera preview if there is no fresh frame, and returns a bounded answer rather than asking a cloud vision model to identify a person.

**Not yet verified:** recognition phrase coverage and routing through the full spoken and typed paths; whether the preview request produces a timely face observation in this turn; unknown-person behavior on live camera; language and Manglish quality of the local answer; desktop UI behavior. The last focused test invocation used system Python and stopped at `ModuleNotFoundError: httpx`, so it did not exercise the code. Find the intended environment/dependencies before running tests. No live camera proof is available from that attempt.

**Recommended next slice:** inspect `decision_router.py`, `live_conversation.py`, `app.py` and the camera/voice tests; add focused tests for supported question variants, camera permission off, camera off/requested, enrolled match, unknown/ambiguous match and route behavior; run them using the project environment; then verify with a live camera only if device access is available. Confirm the exact user-facing phrasing for each recognized language, while keeping displayed text in Manglish. Do not broaden automatic surveillance or run the camera continuously because of this request.

## How to annotate code

Do **not** add comments to every line or mechanically paraphrase function names. That creates noise and quickly becomes stale. Add a short module/function docstring or nearby comment where it explains a non-obvious invariant, permission boundary, data provenance, provider fallback rule, concurrency/lifecycle constraint, or a subtle reason for behavior. Keep types and function names clear; place longer rationale, flow maps and research in `docs/`, linked from this handoff. When behavior changes, update the relevant doc and tests together.

## Run and verification notes

From the workspace root, the README documents:

```powershell
python setta.py
python -m unittest discover -s tests -v
python tools/verify_hub.py
```

The launcher is `tools/start.ps1`; it checks the saved process ID before starting a second camera-owning instance. Confirm runtime logs under `runtime/` and the active Python environment before diagnosing provider or camera failures. This handoff itself is documentation, not a claim that the app or current identity route passed tests.

## Research basis for this handoff format

The format keeps a compact current-state summary, code map, completed/current work, evidence, pending steps, constraints and useful sources. OpenAI's Codex material recommends using repository instructions as a concise map into durable documentation, not a giant instruction dump; its workflow cookbook describes optional project instructions and phase-specific context files. A public agent handoff template independently emphasizes current state, critical files, decisions, pending work, immediate steps, environment, and secrets hygiene. These are conventions, not mandatory filenames; for this project a dated handoff in `docs/` is more appropriate than embedding the whole project history into a root-level `AGENTS.md`.

- [OpenAI: Harness engineering and repository knowledge](https://openai.com/index/harness-engineering/)
- [OpenAI Cookbook: Iterating development workflows with Codex](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex)
- [Agent Toolkit: Handoff template](https://github.com/softaworks/agent-toolkit/blob/main/skills/session-handoff/references/handoff-template.md)
- [Agent READMEs: empirical study of coding-agent context files](https://leo-lihao.github.io/files/P15.pdf)

The Agent Reach environment check found GitHub CLI installed but unauthenticated and Exa search unavailable; public web pages were used for research. GitHub-specific repository/API claims were therefore not independently checked against private GitHub state.

## Refresh this handoff

Update the date and evidence whenever a substantial task changes the active status, key paths, provider/permission boundary, test result or immediate next step. Link to the detailed task document instead of copying its full history here. Clearly label each item **implemented**, **verified**, **unverified** or **planned**. Never add key values, personal face data or private recordings.
