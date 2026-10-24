# PROJECT SETTA

> **Some evenings, the first voice you wish you could hear is the one that used to ask, “How was your day?”**

Setta began with that feeling.

## The story behind Setta

Have you ever missed someone so much that hearing their voice, even for a moment, could change the shape of your day?

For me, it was my mother. My memories of her are limited, but I remember her every day. I come home and there is no one waiting to ask how my day went. Sometimes all I wanted was her voice, in her familiar tone, asking how I was.

The first time I heard a generated version of her voice, I felt a joy and satisfaction I had not expected. That moment is why I started this project. Setta is personal before it is anything else.

I can also imagine a long-distance couple, both busy with work, wanting a familiar check-in at the end of the day. Or someone living alone who would appreciate a gentle conversation. The possible use cases are different, but the human wish for connection is familiar.

Setta does not bring someone back, and it cannot replace a real relationship. It is an attempt to make a small part of memory easier to reach.

## A personal project, with real responsibility

I have seen people cry when they hear a loved one’s voice or see a pixelated version of them on a screen. Those moments can hold joy, grief, longing, and comfort at once. I believe this technology may offer a meaningful moment to some people.

I also worry that an always-available companion could become a substitute for living relationships or something a person finds hard to step away from. I have not solved how to prevent that. Setta does not yet have a validated system to detect or prevent unhealthy dependence. That is an open product and research question, not a solved feature.

Use only voice recordings and images you have permission to use. Be thoughtful about consent, privacy, and how emotionally sensitive these materials are. A generated voice is an approximation, not the person.

## What Setta can do

Setta is a Windows desktop companion built with Python, Tkinter, and CustomTkinter. It combines an animated desktop character with a companion hub.

- **Conversation:** type in the Conversation page or use the optional spoken conversation flow.
- **Multilingual voice:** the Sarvam route recognizes Malayalam, English, and Hindi, generates a reply in the detected language, and speaks it with a configured voice. Malayalam-English code-mixing is supported by the voice flow.
- **Personalization and memory:** configure the companion’s name, persona, speaking preferences, and confirmed facts. Conversation and memory data are stored locally; selected context is sent to the configured reply provider when generating a response.
- **Reminders:** create water and habit reminders. They run while Setta is open and rely on your confirmation; camera proof is not collected.
- **Camera and People:** camera preview and face enrollment are started by the user. Face processing uses local models; camera capture is not continuously enabled by default.
- **Connections:** optionally connect a Google Calendar desktop OAuth client for read-only primary-calendar events. The app does not bundle Google credentials.

The application code is in `src/`, with `setta.py` as the desktop entry point. This is an actively evolving personal prototype, not a polished or supported consumer product.

## Technical feasibility and architecture

The current voice experience is feasible with a modular pipeline: microphone input → speech recognition and language detection → conversation routing and local actions → reply generation → speech synthesis → playback. Speech services and reply models are separate, so the reply provider can change without changing the selected voice provider.

| Capability | Current implementation | Dependencies and limits |
| --- | --- | --- |
| Desktop character and hub | Windows desktop app with animated character and Home, Conversation, Reminders, Camera, Connections, Personality, and Settings pages | Python desktop dependencies; Windows-specific behavior is not verified on macOS or Linux |
| Typed conversation | Local UI connected to the companion conversation flow | Needs configured provider credentials and internet for cloud-backed replies |
| Spoken conversation | Sarvam speech recognition and cloned-voice synthesis; OpenAI, Groq, or Sarvam can provide replies | Requires network, API access/credits, microphone and speakers; physical-device behavior depends on hardware and permissions |
| Voice identity | Sarvam voice IDs are selected in local `config/voice.json` | A voice must first be created/configured through an authorized provider workflow; this repository does not bundle private recordings or voice IDs |
| Camera and face enrollment | User-started camera preview and local face enrollment/recognition | MediaPipe model files are not included; local camera/model setup is required |
| Calendar | Optional Google Calendar connection with read-only primary-calendar access | Requires your own Google Desktop OAuth client JSON and browser sign-in |
| Data storage | Local SQLite and configuration files for app data, conversation, reminders, and preferences | Local storage is not the same as encrypted storage or an off-device backup; protect the Windows account and device |

### Voice quality

The reference used for my current voice was taken from a teaching or explainer video. The generated voice can sound slow or overly measured. Pacing can be adjusted, but natural, expressive speech is difficult to reproduce. Clean, representative, consented audio can improve the result, but it cannot guarantee a natural clone.

### Privacy and network behavior

- Microphone audio is sent to Sarvam while voice conversation is active so it can be transcribed. Do not enable voice mode unless you are comfortable with that provider processing the audio.
- Recognized text, bounded conversation context, and instructions are sent to the selected reply provider. Sarvam also receives text for cloned speech synthesis. Provider retention and data handling are governed by those providers’ terms.
- Local conversation and profile data are stored on the device. Camera preview and face enrollment use local processing; camera capture starts only when requested in the app.
- Google Calendar is optional and read-only in this integration. OAuth tokens are protected with Windows DPAPI.
- `.env`, private configuration, recordings, enrolled-face data, conversation data, and generated runtime files must stay out of version control. No off-device backup is configured by this project.

## Requirements

- Windows 10 or 11 desktop (the application uses Windows-specific APIs and behaviors)
- Python 3 with `pip`; Python's Tk support is needed for the desktop UI
- Internet access for cloud speech, reply, and optional calendar services
- Microphone and speakers for spoken conversation
- Optional: MediaPipe face/hand model files for camera features
- Optional: Google Desktop OAuth client JSON for Calendar

A clean installation from a fresh clone has not been verified. Python package compatibility may depend on the selected Python version and Windows audio/device drivers.

## Installation

Open PowerShell in the project folder. Create and activate a virtual environment, then install the project dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, you can invoke the environment's interpreter directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy the safe example configuration files:

```powershell
Copy-Item .env.example .env
Copy-Item config/amma.example.json config/amma.json
Copy-Item config/voice.example.json config/voice.json
```

Edit `.env` and the local JSON files as needed. These live configuration files are ignored by Git. Never commit API keys, authorized voice IDs, private audio, face data, or personal conversation data.

### Configure voice and reply providers

At minimum, add a valid `SARVAM_API_KEY` to `.env` and authorized Sarvam voice IDs to `config/voice.json` to enable the current Sarvam speech flow. Voice IDs are provider-specific; do not copy IDs from another account. Configure a reply provider in `.env`:

| Variable | Purpose |
| --- | --- |
| `SARVAM_API_KEY` | Sarvam speech recognition and cloned-voice speech; also used for Sarvam replies when selected |
| `REPLY_PROVIDER` | `auto`, `openai`, `groq`, or `sarvam` |
| `OPENAI_API_KEY` | Required when using OpenAI replies or `auto` with OpenAI |
| `OPENAI_MODEL` / `OPENAI_DEEP_MODEL` | OpenAI fast/deep reply models; defaults are set in `.env.example` |
| `GROQ_API_KEY` / `GROQ_MODEL` | Groq reply provider and model |
| `SETTA_API_KEY` | OpenRouter key for the existing standalone text-chat route |
| `GEMINI_API_KEY` | Legacy/experimental Gemini voice route when Sarvam is not configured |
| `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY`, `OMNIROUTE_MODEL` | Optional local reply fallback; requires a separately running and configured OmniRoute service |

With `REPLY_PROVIDER=auto`, the current router uses the configured OpenAI/Groq credentials and selects a reply tier based on the request. For a simpler setup, choose one provider explicitly and provide its key. Shell environment variables take precedence over values in `.env`. Restart Setta after changing provider configuration.

To configure Amma's name, persona, language preferences, and other profile settings, edit `config/amma.json` or use the app's Personality and Settings pages. The example file is the safe template.

### Optional camera setup

Camera features require the MediaPipe face and hand landmarker model files under `assets/models/`. The model files are not included in this repository because redistribution terms have not been verified. Obtain model files from a source whose license permits your use, and consult the camera documentation before enabling those features.

### Optional Google Calendar setup

Create your own Google OAuth Desktop client credentials in Google Cloud Console, then add them through the Connections page. The connection is optional and reads primary-calendar events; tokens are protected with Windows DPAPI. No Google OAuth client secret is bundled with Setta.

## Run Setta

Launch the desktop app from the project folder:

```powershell
python setta.py
```

Or double-click **Open Amma.vbs**, or start it in the background with logs under the ignored `runtime/` directory:

```powershell
.\tools\start.ps1
```

Setta opens the companion hub. The animated desktop character can reopen it using **Open Setta**. Closing the hub leaves the character running; use **Quit Setta** to exit.

### Use conversation and voice

- Open **Conversation** in the hub to send a typed message.
- For spoken conversation, right-click the desktop character and choose **Enable spoken replies**, then **Voice Chat (Alt+M)**. The microphone remains off until voice chat is activated.
- Speak Malayalam, English, Hindi, or Malayalam mixed with English. The app detects language per turn and uses the configured voice for speech output.
- Choose **Stop Voice Chat (Alt+M)** to end microphone capture. Use the voice menu's mute option to turn spoken replies off.
- The microphone and speakers must be available to Windows, and the cloud providers must be reachable. Stop or disable voice mode when you do not want audio sent for processing.

Use the hub's **Reminders**, **Camera**, **Connections**, **Personality**, and **Settings** pages to configure those features. Camera preview starts only when requested. See the documentation links below for detailed behavior and current limits.

## Configuration files and local data

- `.env.example` — safe environment-variable template; copy to ignored `.env`.
- `config/amma.example.json` — safe persona/profile template; copy to ignored `config/amma.json`.
- `config/voice.example.json` — safe voice-routing template; copy to ignored `config/voice.json` and add your own authorized voice IDs.
- `data/` — local conversation memory, reminders, profiles, and enrolled face data; ignored by Git.
- `runtime/` — logs, temporary speech files, and runtime state; ignored by Git.

The app does not train a foundation model on your profile. Local conversation context may be selected and sent to the configured provider to answer a turn. Review provider policies and keep your device account protected. Do not share local data folders as if they were public sample data.

## Development and verification

Install the application requirements as above. Run the local regression suite with:

```powershell
python -m unittest discover -s tests -v
```

For an isolated interface check without camera or provider calls:

```powershell
python tools/verify_hub.py
```

Provider scripts under `tools/voice/` can perform additional checks, some of which call paid or rate-limited services. Read each script's `--help` and source before running it. Synthetic-audio provider checks do not verify a physical microphone, speaker playback, or a complete user conversation. A fresh-clone install, packaged installer, and cross-platform build are not currently verified.

## Known limitations and next work

- Voice naturalness, pacing, pronunciation, and filler behavior depend on the voice sample and provider. A generated voice is not the person.
- The UI/UX needs significant improvement; navigation and visual polish are still evolving.
- Healthy-use boundaries and dependency prevention are unresolved. No clinical or therapeutic role is claimed.
- Camera model files are external, and camera/device behavior depends on Windows, installed models, permissions, and hardware.
- Cloud conversation requires provider availability, network access, account access, and possibly paid credits. No latency, availability, or output-quality guarantee is made.
- A clean-clone setup, packaged release, and macOS/Linux compatibility have not been verified.

## Project structure

```text
PROJECT SETTA/
├── setta.py                   Desktop application entry point
├── requirements.txt           Python dependencies
├── src/                       Application, UI, voice, memory, camera, and integrations
├── config/                    Safe example configuration files
├── assets/                    Character artwork, sounds, and optional model locations
├── tools/                     Launchers, voice utilities, and verification helpers
├── tests/                     Local regression tests
├── docs/                      Product, design, voice, and implementation notes
├── data/                      Ignored local profiles, face data, memory, and reminders
└── runtime/                   Ignored logs and temporary runtime files
```

## Documentation

- [Agent handoff and current implementation map](docs/agent-handoff-2026-10-22.md)
- [Automatic voice conversation: setup, privacy, and verification limits](docs/voice/automatic-conversation.md)
- [Mother voice status and reference workflow](docs/voice/mother-voice-status.md)
- [Current People and face workflow](docs/real-people-discovery-2026-10-22.md)
- [Personality and memory guide](docs/companion/amma-profile.md)
- [Google Calendar and modern app research](docs/companion-app-research-2026-10-21.md)
- [Camera and Settings design notes](docs/design/camera-settings/README.md)

## License and third-party assets

Original application code is licensed under the MIT License; see [LICENSE](LICENSE). Character artwork, model weights, and third-party assets may have separate terms and are not covered by the code license. Check the relevant terms before use or redistribution.

---

*I started Setta because sometimes I just wanted to hear my mother's voice and be asked how my day was. I am sharing it because I know that longing is not mine alone—and because building for it deserves care.*
