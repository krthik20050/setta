# PROJECT SETTA

## Public repository setup

This repository contains application code, tests, research documentation and
runtime-referenced character artwork. Private configuration, cloned voice IDs,
recordings, face data, conversation history and generated previews stay local.
Documentation may refer to these excluded files; they are not bundled here.

Before running a new clone, copy `.env.example` to `.env` and
`config/amma.example.json` to `config/amma.json`. For cloned voice conversation,
copy `config/voice.example.json` to `config/voice.json` and supply your own
authorized Sarvam voice IDs and API key. Camera features also need the MediaPipe
face and hand landmarker models under `assets/models/`; model binaries are not
included pending redistribution-license review. Local sound files and private
sound assignments are not included. A fresh-clone install is not yet verified.

Original application code is MIT-licensed; see `LICENSE`. Character artwork and
third-party assets/model weights are not covered by that license. The project's
dated research documents preserve its development history.

A Windows desktop companion built around the mother's character artwork. Application code is in `src/`. Sarvam voice mode now detects Malayalam, English or Hindi per turn, generates a reply in that language and speaks using the selected cloned voice. Restart older running instances to load the new source.

## Desktop app window

Double-click `Open Amma.vbs` or run `python setta.py` to open Setta's Home window.
Home, Conversation, Reminders and Settings share the existing companion controller.
Click **Open Setta** above the desktop character or double-click her to reopen it.
Closing the hub leaves the character running; use **Quit Setta** to stop the app.
If the character is hidden, closing the hub minimizes it to the taskbar for recovery.
The Windows instance guard prevents a second camera-owning copy of this build.

The modern interface uses CustomTkinter with Home, Conversation, Reminders, Camera,
Connections and Settings. Displayed Malayalam defaults to Manglish; choose native
Malayalam in Settings without changing the stored conversation or speech.
Face enrollment is an inline Camera flow, including the name and status.
Google Calendar can be configured in Connections using your own Desktop OAuth client
JSON, then browser sign-in, access testing and read-only primary-calendar events.
Tokens are protected with Windows DPAPI. No Google client is bundled in this personal build.

Water reminders are configured on Reminders and persist in `data/reminders.sqlite`.
They run while Setta is open, with Done, Snooze and Skip confirmations; no camera proof
or automatic audio is used. Natural-language reminder creation, WhatsApp notification
collection, a native tray icon and an installer remain future work.
Hands-free microphone and screen sharing still open the existing browser page explicitly.
See [implementation research](docs/companion-app-research-2026-10-21.md).
Run `python tools/verify_hub.py` for isolated UI verification without camera/provider calls.

## Environment configuration

**Amma's personality and greeting profile:** [`config/amma.json`](config/amma.json). Change her name, role, how she addresses you, confirmed facts and custom instructions there. See [Amma profile and memory guide](docs/companion/amma-profile.md). This private JSON is ignored by Git; `config/amma.example.json` is the safe template.

**Put your private API keys in [`.env`](.env) at the project root, beside this README and `setta.py`.** It already exists with blank entries. [`.env.example`](.env.example) is the safe template.

Exact location: `D:\projects codes\PROJECT SETTA\.env`

- `SETTA_API_KEY`: OpenRouter text chat.
- `GEMINI_API_KEY`: existing experimental Gemini voice conversation.
- `SARVAM_API_KEY`: automatic-language cloned voice conversation and voice experiments. When configured, this voice route takes priority over the legacy Gemini voice route.
- `OPENAI_API_KEY`: when set, OpenAI generates voice-conversation replies; Sarvam still handles recognition and cloned speech. Leave blank to keep the existing Sarvam reply model.
- `OPENAI_MODEL`: OpenAI reply model, initially `gpt-4.1-mini`; editable independently of the cloned voice.
- `REPLY_PROVIDER=groq`: current explicit reply backend. `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-20b` power replies; Sarvam handles language recognition and cloned speech. This selection takes precedence over a saved OpenAI key. Use `openai` or `sarvam` only when intentionally switching providers.

`setta.py` loads this exact file regardless of terminal working directory. Existing shell variables take precedence. Never commit real keys or put them in documentation.

## Folder map

```text
PROJECT SETTA/
  .env                         Private keys (ignored)
  .env.example                 Safe blank template
  setta.py                     Application entry point
  requirements.txt             Desktop Python dependencies
  src/                         Application code
    paths.py                   Shared asset/data/config locations
  assets/
    models/                    Face and hand detection models
    sounds/                    Built-in sounds
    mother/
      artwork/                 Mother source sheets and approved poses
      animations/              Exported animation previews
      voice/
        originals/             Eight full audio tracks and metadata
        shortlist/             Listening page and candidate WAV clips
        references/
          approved-2026-10-20/  Your selected references: 6, 7 and 8
  config/
    sounds.json                Existing sound assignments
  data/
    known_faces/               Private face embeddings (ignored)
  runtime/                     Logs and process ID (ignored)
  tools/
    start.ps1                  Background Windows launcher
    voice/
      shortlist_voice.py       Reference screening/transcription
      requirements.txt         Optional audio dependencies
  tests/                       Regression tests
  docs/
    voice/                     Voice research and storage inventory
    companion/                 Character/interaction research
    history/                   Earlier plans and updates
  .tools/                      Local downloader installation (ignored)
```

Two old model files immediately under `assets/` are temporarily retained because the running camera process locks them. The background launcher removes matching old copies after that process exits. Hidden tooling folders and Python caches are tool-managed.

## Run

Use your existing Python environment, or create a virtual environment first. No new environment was created during cleanup.

```powershell
python -m pip install -r requirements.txt
python setta.py
# Or launch in the background with runtime logs:
.\tools\start.ps1
# Regression tests:
python -m unittest discover -s tests -v
```

Optional audio work also needs FFmpeg on PATH:

```powershell
python -m pip install -r tools/voice/requirements.txt
python tools/voice/shortlist_voice.py
# Requires an already cached Whisper model:
python tools/voice/shortlist_voice.py --transcribe
python -m http.server 8767 --bind 127.0.0.1 --directory assets/mother/voice/shortlist
```

Open `http://127.0.0.1:8767/listen.html` while the server is running. Regenerating the shortlist does not overwrite the separately saved approved references.

## Documentation

- [Agent handoff: code map, product boundaries, current identity route and verification status](docs/agent-handoff-2026-10-22.md)
- [Agentic desktop roadmap: phases, skills, decision model, execution and reverse-engineering](docs/agentic-desktop-roadmap.md)

- [Current People workflow: capture real faces, label them and recognize them](docs/real-people-discovery-2026-10-22.md)

- [Google Photos People & pets research and Setta adaptation](docs/google-photos-people-pets-research-2026-10-22.md)

- [Retired screenshot-copy approach (superseded)](docs/reference-people-recreation-2026-10-22.md)

- [Photo-first People gallery, portrait assignment and missing-image backfill](docs/people-portrait-gallery-2026-10-22.md)

- [Face grid, preview-first camera, chat-history cards and conversational reminders](docs/chat-history-camera-reminders-2026-10-21.md)

- [Current stack, compact theme controls, reviewed face samples and chat improvements](docs/compact-controls-face-learning-2026-10-21.md)

- [Approved Camera and Settings redesign: design, flows, privacy, tests and limitations](docs/design/camera-settings/README.md)

- [Voice status, exact paths, and next cloning step](docs/voice/mother-voice-status.md)
- [Video sources and consent](docs/voice/mother-voice-references.md)
- [Screening method](docs/voice/mother-voice-shortlist-method.md)
- [Provider research](docs/voice/mother-voice-research-2026-10-20.md)
- [Sarvam comparison run and generated audio records](docs/voice/sarvam-comparison.md)
- [Longer Malayalam and mixed-language comparison](docs/voice/sarvam-extended-comparison.md)
- [Automatic-language conversation: usage, privacy and verification](docs/voice/automatic-conversation.md)
- [Voice failure fix, cloud bubble and speaking animation](docs/voice/voice-failure-and-thought-bubble.md)
- [Folder changes and verification](docs/folder-reorganization.md)

Private audio, face data and credentials remain local; no off-device backup is verified. Existing external Downloads sound paths are preserved and remain a portability limitation. Dependency lists reflect imports and are not verified in a clean environment.
# Open Amma on your laptop

Double-click **Open Amma.vbs** in this folder, or the **Amma** desktop shortcut.
It starts the companion and opens http://127.0.0.1:8770/ in your default browser.
Click **Start** on the voice page and allow microphone access when prompted.
Keep the project folder in its current location so the desktop shortcut continues to work.
Internet access is required for Groq and Sarvam. Keys stay in the project's `.env` file.
Use **Stop mic** to stop listening; close the companion to exit the desktop app.
Startup errors appear in a dialog; detailed app logs are under `runtime/`.
