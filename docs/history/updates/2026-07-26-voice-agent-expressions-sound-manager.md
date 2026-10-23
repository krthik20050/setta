# Session Update — 2026-07-26

## Voice AI Agent (Alt+M)
- `src/voice.py`: Global **Alt+M** hotkey via `keyboard` lib
- **STT**: `speech_recognition` Google Web Speech API
- **LLM**: Gemini streaming via `google-genai` (2.0-flash), sentence-boundary detection
- **TTS**: `edge-tts` (JennyNeural) — plays per-sentence, streaming
- **Auto-relisten** loop after response completes
- Graceful fallback: Gemini 429 quota error shown in speech bubble, OpenRouter text chat still works
- Voice callbacks wired into `PetApp`: `_voice_on_state`, `_voice_on_text`, `_voice_on_final`
- Mapping: `voice_listening` → `run` animation, `voice_thinking` → `review` animation
- New dependencies: `google-genai`, `SpeechRecognition`, `edge-tts`, `keyboard`
- Tested both Gemini API keys — both return 429 `limit:0` (needs free tier activation at aistudio.google.com)

## Expression / Emotion Detection
- `src/webcam.py`: Added `_update_mood(bs)` with rolling buffer (10 frames ~1s)
- Moods detected via MediaPipe face blendshapes:
  - **Happy**: `mouthSmileLeft/Right` > 0.15
  - **Sad**: `browDownLeft/Right` > 0.3
  - **Surprised**: `jawOpen` > 0.2
- Fallback for raw landmarks when blendshapes unavailable (smile ratio, mouth open)
- `self.face_emotion` set from `self.current_mood` for camera overlay display
- `src/app.py`: Mood wired into animation loop:
  - **Happy** → wave animation + "Happy to see you!" bubble
  - **Sad** → failed animation + "Don't be sad..." bubble
  - **Surprised** → run animation + "Whoa!" bubble
- Smoothed with 5s cooldown, only triggers when pet is idle
- `_last_mood` tracking fixed to only update during idle state (prevents missed transitions)

## Sound Manager
- `src/sound_manager.py`: New module for assigning custom sounds to pet actions
- `assets/sounds_config.json` stores user mappings (JSON)
- 7 assignable actions: `greeting`, `face_detected`, `happy`, `sad`, `surprised`, `jump`, `stretch`
- **Modern UI/UX rebuild** (plain tkinter, dark theme `#0d0d1a`):
  - Custom `HoverButton` class — canvas-drawn rounded-rect buttons with hover states
  - Card-based layout with `#1a1a30` cards, `#2a2a4a` borders
  - Green ● + "Custom" badge when a file is assigned
  - Gray ● + "Default" badge for built-in defaults
  - Shows filename + full file path for assigned sounds
  - Browse / Play / Clear buttons per action
  - Custom-styled scrollbar, centered over parent window
- `play_action_sound(action)` helper — prefers custom file, falls back to built-in greeting.wav
- Right-click menu: Sound Manager option
- Supports `.wav` (winsound) and `.mp3` (winmm MCI)

## Refactoring
- Monolith `setta.py` split into `src/{app,chat,face_id,webcam,voice,sound_manager}.py` + `assets/`
- `winsound` import removed from `app.py` (moved to sound_manager)
- All imports and syntax verified across all modules

## Dependencies Added (pip)
- `google-genai`, `SpeechRecognition`, `edge-tts`, `keyboard`, `customtkinter`

## Known Issues
- Gemini API keys return 429 `limit:0` — user must activate free tier at aistudio.google.com
- OpenRouter fallback chat works fine
- cp1252 encoding caveat: emoji characters handled via explicit utf-8 encoding
- Hardcoded API keys removed from source — use `SETTA_API_KEY` and `GEMINI_API_KEY` env vars
