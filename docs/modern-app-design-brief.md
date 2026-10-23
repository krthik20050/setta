# Setta modern desktop app design brief

Date: 2026-10-21. This brief records user direction and current source observations, not an installed product capability claim.

## Product and audience

Setta is a personal Windows companion represented by the user's mother. It combines a quiet desktop presence with conversation, local memory, contextual assistance and reminders. The user is new to desktop application design and needs visible everyday controls rather than nested right-click menus. The app must feel like a familiar place to talk to Amma, not a developer console or a generic pet configuration utility.

The mother character and her recognizable face are the primary identity. Preserve the exact approved likeness from `assets/mother/artwork/mother-likeness-v6.png`. Do not regenerate or reshape her face as part of interface work. Keep a clear face alongside full-body movement. Speech and status must never cover her face.

## Explicit user direction

- A proper modern application with the character prominent on its home page, while the same companion remains available on the desktop.
- A live home avatar, rather than only static portraits or two disconnected character images.
- Camera preview and face enrollment inside the application. No separate enrollment prompts, confirmation windows or preview popups in this main flow.
- Connections as a visible navigation destination.
- Manglish as the default displayed conversation, with an explicit native-script option.
- Reminders such as regular water check-ins, with clear confirmation and snooze controls.
- Google Calendar first; summarize new WhatsApp desktop notifications first. These are integration targets, not evidence they are connected.
- Preserve existing Sarvam voice/language work and the previously requested muted audio state.

## Visual direction

Physical scene: a person working at a Windows laptop during the day glances at a caring familiar companion, then opens the app for a focused conversation or quick adjustment.

Use a light neutral canvas with a restrained emerald accent, softly rounded surfaces and substantial readable typography. Suggested starting colors: canvas `#F5F7F4`, surface `#FCFDFC`, alternate surface `#EAF0EB`, ink `#203A2B`, muted text `#53675A`, emerald `#236544`. Use the accent for the selected navigation item, main action and meaningful active states. Avoid a heavy dark sidebar, gradients, decorative glass effects, excessive badges, uniform dashboard tiles and nested cards.

Use Segoe UI for Windows UI text; Nirmala UI where native scripts require it. Maintain strong focus indicators, readable contrast and clear disabled states. Content should remain usable at 840 by 600 and on a 1366 by 768 laptop with display scaling. Long settings pages need scrolling; the conversation needs a stable composer and scrollable transcript.

## Information architecture

Navigation: Home, Conversation, Reminders, Connections, Settings. Keep camera access discoverable from Home and Settings; it may have an inline section without adding another navigation destination.

### Home

Make one live mother avatar the visual center. Animate from the same approved asset/state system used by the desktop companion; a subtle idle state is enough. Display genuine conversation state nearby: Ready, Listening, Thinking or Unavailable. Do not use a fabricated connected state.

Provide a clear conversation entry, Return to desktop action and quiet movement controls. Beneath the main character area, show useful task-based content such as the next actual water check-in, an available camera setup action, or a connection that still needs setup. Cards are justified only when they group a task and its action. Do not fill empty space with fake activity, scores or generic statistics.

### Conversation

Provide an accessible transcript and visible text composer with Send. Default rendered replies to Manglish while keeping raw memory text and provider language intact. Native script is an explicit display choice, persisted separately from shared voice configuration. Switching display mode must not alter speech pronunciation settings or corrupt stored text.

Show live incoming messages while the page is open, avoiding duplicates from locally inserted turns and refreshed memory. Clearly distinguish a failed reply from a saved reply. Typed messages must not turn on the microphone. Keep microphone and output controls explicit; a native app control must not claim to stop a separate browser capture unless it actually does.

### Camera and face enrollment

Use an inline preview from the existing camera capture, not another `VideoCapture` instance. Show meaningful availability and error text. A name field, capture/enroll action, progress state and inline success/failure belong together. Validate the face sample before submission. Run recognition/enrollment work off the Tk UI thread, return results through the existing main-thread queue or `after`, and cancel preview updates when the view is destroyed.

Do not call the old `_toggle_cam` or `_register_current_face` flows as the app's primary enrollment path if those launch popups. Keep legacy shortcuts compatible while extracting a reusable callback/service where needed. Face activity is a visible cue, not proof of emotion, intent or water consumption.

### Reminders

Provide interval entry, next due time and one clear active/paused state. Enable Done, Snooze and Skip only for a pending check-in, or explain unavailable actions inline. Persist timing locally, avoid replaying missed intervals in a burst, and disclose that checks run while Setta is running. Camera proof is optional future functionality, not a requirement for acknowledging water.

### Connections

Give Google Calendar and WhatsApp notifications distinct connection rows with actual states and next actions. Until implementations exist, state Not connected or Not installed. Do not display a Connect button that merely fakes success. Explain that calendar access requires Setta's own account authorization, and notification summaries only cover snippets Windows received.

### Settings

Group desktop visibility/movement, display language and conversation/privacy controls. Apply changes immediately to the same companion. Synchronize actual walking state with visible controls; returning from a hidden desktop must not leave a checked Walking setting while movement is stopped. Retain a reliable reopen route when the companion is hidden. Close, Hide and Quit need distinct behavior and wording.

## Implementation constraints and current evidence

The inspected `src/companion_hub.py` uses a Tk `Toplevel` sharing `PetApp` and its Tk loop. `src/app.py` owns camera capture, conversation, voice and desktop animation. Preserve this ownership when modernizing with CustomTkinter: use `CTkToplevel` and compatible image wrappers as needed; do not construct a second root, voice agent, conversation session or camera worker.

The existing Home uses static full-body and portrait images. The existing camera actions invoke legacy popup functions. Connections are currently only text in Settings. The existing desktop speech bubble converts displayed text with `to_manglish`, while the hub transcript needs its own reversible display rendering. The current source is changing concurrently; verify these points against the latest file before editing.

CustomTkinter improves widget consistency but does not itself provide animation, native tray lifecycle, OAuth, notification access or accessible keyboard behavior. Validate these separately. Keep image references alive, scale PIL images deliberately, and schedule animation through the existing Tk loop with cancellable timer IDs.

## Reference patterns

- Open-LLM-VTuber documents normal and desktop-pet modes sharing conversation and application state: https://docs.llmvtuber.com/en/docs/user-guide/frontend/electron/
- Rainmeter documents a central Manage window, remembered desktop positions and tray recovery: https://docs.rainmeter.net/manual/getting-started/using-rainmeter/
- Open-LLM-VTuber's open-source implementation is a reference for the dual-surface model, not a reason to replace Setta or import a different character: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber

## Completion checks

1. Home shows the approved mother likeness with visible animation and unobstructed face.
2. Camera preview, name entry, enrollment progress and result remain in the app.
3. Conversation defaults to Manglish; native-script selection changes display without rewriting memory or voice configuration.
4. Connections has its own destination and truthful unavailable states.
5. Reopening the app does not duplicate services; hiding, movement controls and Quit behave consistently.
6. Short laptop layouts, keyboard navigation, microphone-off state and service failures are checked in the actual running app.
