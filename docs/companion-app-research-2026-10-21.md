# Setta companion application research

Research date: 21 October 2026. This is an engineering research panel synthesis, not interviews with named human experts. External projects were reviewed through official documentation and GitHub pages; they were not installed or exercised on this laptop.

## Decision

Build an additive application window using `tkinter.Toplevel` on Setta's existing Tk event loop. Give Amma a clear home, a conversation view, visible settings and a water-reminder workflow. Keep the working desktop companion and its animation controller. Use the existing conversation and settings interfaces rather than duplicating the intelligence or voice stack.

This delivery scope is a control center with Home, Conversation and Settings, plus configurable water reminders and confirmation/snooze/skip. Google Calendar and WhatsApp notification ingestion remain separate integrations. Camera evidence is optional and uncertain; it must not be treated as proof of hydration or grounds to accuse the user of lying.

## Panel findings

| Perspective | Finding | Consequence |
| --- | --- | --- |
| Product and interaction | A companion needs both a visible home and a quiet desktop presence. | Put primary actions in the app; retain right-click as a shortcut. Keep speech bubbles beside the character. |
| Desktop engineering | Existing Tk windows can share one interpreter and controller. Mixing independent GUI event loops adds coordination cost. | Add a Toplevel now; keep UI mutation on the Tk thread. |
| Conversation architecture | Window and desktop modes should share one conversation and settings state. | Reuse existing services and callbacks; avoid a second assistant session. |
| Reliability | Hiding a window, hiding the avatar, pausing and quitting are different actions. | Label them explicitly and provide an obvious route back into the app. |
| Privacy and reminders | Scheduled check-ins should have deterministic timing and user-controlled confirmation. | Persist reminder state, allow snooze/skip, bound escalation and preserve audio preferences. |

## Framework comparison

| Framework | Strengths | Setta-specific costs | Decision |
| --- | --- | --- | --- |
| Tkinter/ttk | Already present; shares avatar controller and event loop; standard Python interface. | Custom layout, styling and accessibility diligence. | Use for this additive build. |
| CustomTkinter | Modern widgets, appearance modes and DPI support. Repository declares MIT. | Another dependency; still the same Tk architecture. | Optional later; not necessary for a first control center. |
| pywebview | HTML/CSS interface driven by Python; BSD-3-Clause. | Own blocking GUI loop; Windows renderer/runtime dependencies; microphone and display capture need testing. | Consider a separate frontend process if web UI reuse later justifies it. |
| PySide6 | Native windows, signals and tray API; mature desktop toolkit. | Qt runtime, packaging and migration; LGPL/GPL/commercial terms and module choices require review. | Strong future option, not a prerequisite. |
| Electron | Tray, single-instance and lifecycle APIs; Electron itself uses MIT terms. | Node/Chromium plus Python sidecar; IPC, permission and security maintenance. | Avoid introducing it solely to obtain an app window. |

Documentation: [Tkinter architecture and threading](https://docs.python.org/3/library/tkinter.html), [CustomTkinter repository](https://github.com/TomSchimansky/CustomTkinter), [pywebview usage and blocking GUI loop](https://pywebview.flowrl.com/guide/usage.html), [pywebview license](https://github.com/r0x0r/pywebview/blob/master/LICENSE), [Qt tray API](https://doc.qt.io/qtforpython-6.11/PySide6/QtWidgets/QSystemTrayIcon.html), [Qt licensing](https://doc.qt.io/qt-6.10/licensing.html), [Electron tray](https://www.electronjs.org/docs/latest/tutorial/tray), [Electron single-instance API](https://www.electronjs.org/docs/latest/api/app), [Electron license](https://github.com/electron/electron/blob/main/LICENSE).

License statements describe upstream declarations, not a completed distribution audit. Bundled engines, models, assets and other dependencies can carry additional conditions.

## Useful GitHub implementations

### Open-LLM-VTuber

Its frontend documents web, window and desktop-pet modes, with window and desktop modes sharing conversation context. This is the useful product pattern for Setta: one companion with multiple presentations. Do not replace the existing language/voice integration or mother artwork merely to reuse another avatar engine. Main project code is MIT; Live2D sample models have separate terms. The current README describes an early v2 rewrite discussion and restricted new v1 feature requests, so any source reuse should pin an inspected revision.

Sources: [repository and current README](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber), [frontend modes](https://docs.llmvtuber.com/en/docs/user-guide/frontend/), [license and Live2D exception](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/main/LICENSE).

### pystray

This is a focused candidate for future tray support. Its documentation permits `Icon.run()` on a secondary thread for Windows-only applications. Callbacks should send commands to a queue processed on Tk's thread; real quit must stop the tray loop. The repository declares LGPL-3.0, not MIT. Its notification API displays notifications; it does not read WhatsApp notifications.

Sources: [repository](https://github.com/moses-palmer/pystray), [threading and framework integration](https://pystray.readthedocs.io/en/latest/usage.html).

### Electron lifecycle patterns

Electron's tray and single-instance examples clarify useful behavior even if Setta does not adopt Electron. Its security guidance also reinforces narrow privileged bridges, explicit permissions and validated IPC. These patterns are references, not imported code.

Source: [official security checklist](https://www.electronjs.org/docs/latest/tutorial/security/).

## Current build versus future lifecycle work

For this additive implementation, use the **Open Setta** entry and companion double-click to recover the control center. A close action should hide this window without silently terminating the companion. Keep an explicit quit action available. Do not describe these routes as a system tray implementation.

The build also adds a Windows named-mutex guard and an explicit launcher restore request. When the desktop character is hidden, closing the hub minimizes it to the taskbar so it stays recoverable. Future work includes a tray icon, startup preference and installer distribution. A future tray must not become another hidden menu that replaces the visible home.

## Verification for this build

The complete existing suite plus reminder and Windows instance-guard tests passed: 107 tests. Sandbox loopback restrictions required running the final suite outside the sandbox with workspace-local temporary files. `tools/verify_hub.py` exercised all four pages, hide/reopen, serial text submission through an injected controller, persistent preferences, water due/snooze/pause and mute preservation. This isolated UI check does not call real providers or capture the camera. The real Windows application was also launched and inspected; it is source execution, not an installer/package test. A fresh live conversation/provider response was not part of this UI verification.

## Acceptance checks

- Home presents Amma with a clear face and visible primary controls.
- Conversation and settings operate on existing application state.
- Closing and reopening the control center preserves the companion.
- Water reminders can be enabled, timed, confirmed, snoozed and skipped; state survives the intended persistence boundary.
- Audio stays governed by the user's existing mute preference.
- No calendar connection, notification access or autonomous desktop control is implied by adding the control center.
- Report source checks, synthetic tests and actual visible Windows behavior separately.

## Research boundaries

Agent-Reach's GitHub CLI route was attempted, but the shell could not reach the GitHub API. Official GitHub pages and vendor documentation were accessed through the web research tool instead. The Agent-Reach update check also failed DNS after retries; nothing was updated. REA routing guidance applies source-analysis tools to these complete source repositories; no packaged competitor reverse engineering or runtime claims were made.
