# Project Setta — Desktop Pet Architecture

## Overview
Windows desktop pet app. Webcam detects hand raise → plays greeting .wav + sprite wave animation. Includes face detection, expression analysis (MediaPipe blendshapes), face recognition (deepface VGGFace), live camera preview, and AI chat via OpenRouter.

## Components

### 1. Webcam Thread (`src/webcam.py` — `WebcamCapture`)
- OpenCV capture + MediaPipe HandLandmarker + FaceLandmarker (0.10.35 tasks API)
- Hand-raised detection: wrist y-coordinate threshold in top 40% of frame
- Gesture/expression detection via face blendshapes: mouth open, smile, frown, blink
- Face landmark overlay on camera preview
- Frame queue for tkinter camera preview window
- Async face-ID trigger every N frames (calls app-layer callback)

### 2. Face ID (`src/face_id.py` — `FaceID`)
- deepface `represent()` (VGGFace) for face embeddings
- Cosine similarity matching against `known_faces/*.npy` (threshold 0.4)
- Registration: captures frame on demand, computes embedding, saves to disk
- Background-threaded to avoid blocking camera loop (`_busy` flag guards stacking)
- Face sound (babu-bhai.mp3 via winmm MCI) — once per session, toggleable

### 3. Pet Window (`src/app.py` — `PetApp`)
- Always-on-top frameless tkinter window (transparent colour #ff00ff)
- MooMew Coder Cat sprites from `assets/spritesheet.webp` (192×208 cells, 8×9 grid)
- Animations: idle (row 0), wave (row 4), run/jump (row 7), review/thinking (row 8), failed/error (row 5)
- Speech bubble with background rect for OpenRouter responses
- Close button (×) with hover effect, window dragging
- Right-click menu: AI Chat, Toggle Camera Preview, Register My Face, Toggle Face Sound, Exit

### 4. Audio System
- `winsound.PlaySound` for greeting.wav playback on hand raise
- `winmm.mciSendStringW` for face-recognition sound (babu-bhai.mp3, non-blocking)

### 5. OpenRouter Client (`src/chat.py` — `chat_with_ai`)
- HTTP POST to `/v1/chat/completions` (non-streaming)
- Configurable model + URL, API key from `SETTA_API_KEY` env var
- Response displayed in pet speech bubble

### 6. Voice Agent (`src/voice.py` — `VoiceAgent`)
- Global hotkey `Alt+M` (via `keyboard` library) toggles voice mode on/off
- Speech-to-text via `speech_recognition` (Google Web Speech API, free, no key)
- AI via Gemini API (`google-genai` SDK, streaming, `gemini-2.0-flash`, `GEMINI_API_KEY` env var)
- Text-to-speech via `edge-tts` (Microsoft Edge voices, free, sentence-by-sentence pipelined with Gemini stream)
- Auto-relisten loop: listen → AI → speak → listen → ... until user exits
- Sentences extracted on `.` `!` `?` boundaries during streaming; each sentence dispatched to TTS immediately while next sentence is still being generated
- Pet animation: run/jump while listening, review/book while thinking
- Custom voice cloning (ElevenLabs/friend voice) deferred to later iteration

## Data Flow
1. Webcam frame → MediaPipe → hand_raised flag
2. Main loop picks up flag → pet waves + plays greeting .wav
3. Optional: AI processes input → streams response
4. Pet returns to idle after 3s

## Sprites
- MooMew Coder Cat (chibi tuxedo cat)
- Source: https://github.com/legeling/awesome-codex-pet
- Single spritesheet.webp, frames extracted by coordinates

## Constraints
- Free for work use (no paid APIs except OpenRouter)
- Windows-first
- Modular: `setta.py` (entry), `src/{app,webcam,face_id,chat,voice}.py` (logic), `assets/` (models, audio, spritesheet)
