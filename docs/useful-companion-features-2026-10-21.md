# Useful companion features — 21 October 2026

Implemented quiet hours, multiple named interval reminders, durable reminder history, and personality backup/import in the existing native app.

## Purpose and flows
- Reminders > Your reminders: add a named habit, select it to edit, pause/resume, confirm, snooze, skip, or archive. Editing restarts its interval and clears an existing pending check-in. Archived reminders retain history.
- Quiet hours: opt-in local reminder suppression, 24-hour times in Asia/Kolkata. A reminder due during quiet hours restarts a full interval after quiet ends (or after waking, if later). This affects Amma reminders, not Windows global notifications or conversation speech.
- Activity: recent 40 reminder events including user reports and scheduler events. Done is self-reported, not camera verification.
- Settings > Amma profile: export only name, role, custom instructions. Import validates a versioned file and shows an inline preview with Apply/Cancel; private chat, credentials, voice and other config stay separate.
- Multiple simultaneous reminders produce one combined speech bubble; each remains pending in Reminders. Home summarizes all active habits.

## Research and review
Microsoft Do Not Disturb informed explicit opt-in scheduled suppression: https://support.microsoft.com/en-us/windows/experience/notifications-and-do-not-disturb-in-windows
Python timezone documentation informed deterministic local-time boundaries and Windows timezone handling: https://docs.python.org/3/library/zoneinfo.html
Specialist backend and UX/code reviewers checked suppression, persistence, simultaneous reminders, and import boundaries.

## Verification
155 unit/integration tests passed. Real-widget isolated hub smoke passed for navigation, reminders, quiet hours, archive/history, and personality import preview/apply. Database-lock latency check: max page switch 69.4 ms, max heartbeat gap 33.5 ms. These are controlled local tests, not a guarantee of provider/hardware latency.
Reminders run while Setta is open. Actual overnight delivery has not been observed end-to-end.
