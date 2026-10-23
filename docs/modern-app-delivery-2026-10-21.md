# Setta modern app iteration

This iteration replaces the legacy Tk/ttk control panel with CustomTkinter presentation while retaining the existing Tk root, avatar controller, conversation service and memory. It does not migrate Sarvam or change the approved mother artwork.

## Delivered flows

- Home: live avatar driven by existing character animation states, approved resting figure and close-up, conversation entry, next water check-in, movement/expression controls and connection entry.
- Conversation: default Manglish display, reversible native Malayalam display, stable composer, current memory-backed conversation. “Enroll my face” opens Camera in place rather than sending a task to the model.
- Reminders: interval presets, editable minutes, inline validation, persistent schedule, disabled confirmation buttons until due, confirm/snooze/skip and pause/resume.
- Camera: inline preview and name form, fresh-frame gate, background embedding generation, inline success/failure. Capture is shared, not duplicated. This still uses the existing single-sample recognition backend; it is not a newly validated advanced recognition model.
- Connections: Google Desktop OAuth client import, browser sign-in with state/PKCE, cancellation, read-only primary-calendar event listing, access check and local disconnect. Client and token data are protected with Windows DPAPI. No developer client is bundled, so real account sign-in requires the owner’s Google OAuth client setup. WhatsApp honestly exposes requirements; its Windows helper is not implemented.
- Settings: persisted Manglish/native script, desktop presence switches, reduced app animation, memory export and voice stop/mute. Original conversation text is stored unchanged; only display rendering changes.

## Research applied

The [Hermes dashboard documentation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/web-dashboard.md) informed the connection-management direction: inspect configuration and verify access rather than assuming saved configuration means a working connection. This is pattern research, not a claim of importing Hermes or supporting its integration catalog.

[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) supplies the modern widget layer under its MIT license. The [button](https://customtkinter.tomschimansky.com/documentation/widgets/button/) and [scrollable frame](https://customtkinter.tomschimansky.com/documentation/widgets/scrollableframe/) documentation guided the implementation. [Google’s desktop quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python) establishes the separate OAuth client and consent setup requirement.

## Validation and limits

111 regression tests passed outside the restricted sandbox, including mock-provider OAuth callback state rejection, PKCE, read-only requests, cancellation, refresh-token retention and real Windows encrypted-storage round-trip. `tools/verify_hub.py` exercised six real widget pages, Manglish/native switching, inline stale-face handling, serial submission, reminders, saved preferences and mute preservation with isolated data and no real provider or camera requests.

The app was launched as a real Windows process. Final screenshot-based visual verification was prevented by the Windows lock screen; no authentication or unlock was attempted. The separate design-review agent hit an account usage limit, so the primary agent completed implementation and review. Live Google account consent, new real face enrollment, packaged installation and WhatsApp notification ingestion remain unverified or unavailable as described above.
