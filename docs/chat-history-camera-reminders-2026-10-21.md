# Face grid, preview-first camera, chat history and spoken reminders

Date: 21 October 2026

## Delivered behavior
- Camera shows a three-column people grid: real saved photo above the person's name and controls. Unknown/missing images are not replaced with invented faces. Add photo opens the file chooser for that label. New camera/photo enrollments save a local face thumbnail.
- The existing known_faces folder contained embeddings only (no reference JPEGs), so those old identities require one clear photo or camera sample to populate their tiles. An embedding cannot reconstruct its source photograph.
- Camera capture publishes raw frames before importing MediaPipe or loading detector models. Frame capture and analysis now have separate owner threads; slow analysis cannot hold up preview. Analysis state appears separately from Camera on. Camera stop is nonblocking on the UI thread; each owner closes its own native resources. A restart waits for the previous owner's shutdown rather than opening a duplicate device.
- Explicit English requests such as Open the camera request the native Camera preview, subject to the existing camera capability permission. A successful request means queued opening, not a claim that hardware is already displaying a frame.
- Sidebar Conversation is now labelled Chat history. It opens dated session cards with first-message titles, start/last-activity times and message counts. Current chat opens the active session; New chat starts a new session while keeping archived messages and confirmed memory. Historical sessions are read-only in this version. No messages are deleted or silently reassigned. Existing session identifiers define legacy grouping, not guessed boundaries. Starting a new chat is blocked during active speech/replies.
- A supported explicit request such as Remind me to drink water in the next five minutes creates a persisted one-time reminder in the same local reminder store used by the app. It is handled before a model reply, for typed and recognized voice input. The response confirms scheduling only after the write succeeds. Timer capability permission applies.
- One-time reminders can be snoozed; Done or Skip disables them rather than repeating the interval. Quiet hours still apply, and Setta must remain open for real-time notifications.

## Implementation
- src/webcam.py: capture/analysis separation, independent analysis state, resource ownership and stop guards.
- src/modern_hub.py: face grid, history cards, session-specific reads, archive/send guards, new-chat flow, preview state.
- src/companion_memory.py: grouped session metadata queries; prior messages preserved.
- src/live_conversation.py: explicit reminder/camera routing and new session creation.
- src/reminder_intent.py: bounded explicit English intent parsing; numerical and common word durations, seconds/minutes/hours, up to 24 hours. This is not unrestricted natural-language scheduling or recurring reminder parsing.
- src/local_reminders.py: additive one_shot SQLite migration and create_once API; legacy interval reminders retained.
- src/app.py: camera-preview callback into the existing Tk controller.

## Verification
- Final full suite: 176 tests passed; expanded real-widget hub smoke passed.
- Focused camera test blocks analysis initialization and checks that preview frames still publish.
- Physical laptop test: first preview frame observed at 1.197 seconds while analysis status was still Loading face analysis. No frames saved, camera stopped and owner exited. This is one measurement, not an across-device startup guarantee; full model readiness can take longer.
- Tests cover durable non-repeating reminders, explicit bounded parsing, actual conversation-path scheduling without provider calls, preserved sessions, and camera request permissions.
- Real-widget smoke covers dated history cards, archived read-only views, active chat isolation, new empty chat and retained archive, as well as existing navigation, enrollment, theme and reminder flows.
- Storage contention latency check: maximum page switch 183.1 ms, heartbeat gap 33.2 ms, chat navigation 63.2 ms. Provider latency not included.
- Existing Sarvam transport, custom voice/provider work, profile permissions and local memory ownership are retained. Model/recognition accuracy is not claimed improved by this layout change.

## Use
1. Camera: choose Add photo on a missing tile, or turn on the camera and save a fresh face under that name.
2. Chat history: choose New chat or Current chat; select a dated card to read an old session.
3. Ask: Remind me to drink water in five minutes. Find the resulting one-time item in Reminders.
