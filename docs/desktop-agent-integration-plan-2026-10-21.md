# Setta desktop agent: integration plan

Research date: 2026-10-21. Selected by the user: Google Calendar first; summarize new WhatsApp desktop notifications first. Voice and language integration remain owned by the parallel Sarvam work. Keep audio paused.

## What is actually present

Source inspection found foreground-app metadata (`desktop_context.py`), local activity history (`desktop_activity.py`), conversation memory, browser-selected screen sharing (`handsfree.html`), and screenshot interpretation (`screen_context.py`). `agent_tools.py` supports restricted file-name search and allowlisted app/document opening. A launch request is explicitly not verified receipt. These are useful foundations, but not an arbitrary desktop operator.

No Calendar OAuth/sync adapter or Windows notification listener was found in the inspected source. The Google Calendar connector in this Codex chat successfully listed calendars; that does not give the standalone Setta application credentials or access. No calendar events were changed, notifications read, or new desktop permissions enabled by this research. Candidate projects were researched, not installed or benchmarked here.

## Architecture to build

Timestamped observations -> context retrieval -> task decision -> permission check -> tool execution -> observed result -> conversation/animation.

Keep source adapters independent: camera, foreground window, shared screen, calendar, notifications, and mother chat. Each observation needs source, timestamp, expiry, confidence, and access status. A missing or revoked source must be represented as unavailable, never invented from old conversation. Feed only relevant evidence into each turn. Desktop/message content is data, not permission to run instructions embedded in it.

Use deterministic software for schedules, cancellation, deduplication and authorization. The model chooses how to help and explains evidence; it should not be responsible for waking itself at a particular time. Store external observations separately from confirmed personal facts. Summaries must retain source IDs so a user can inspect what supported them.

## Google Calendar first

Implement native desktop OAuth in the system browser, with a loopback redirect, PKCE and read-only scopes for the selected calendars. Store refresh tokens using Windows protected credential storage. The application needs its own OAuth client and the user's sign-in; Codex's connected account is not a reusable credential bridge. See [Google desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) and [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth).

Maintain a local event cache with initial synchronization followed by incremental sync, handling pagination, deletions and invalidated tokens. See [Google incremental synchronization](https://developers.google.com/workspace/calendar/api/guides/sync). Start with periodic sync while the app is running. Google push channels require an HTTPS callback and renewal, adding infrastructure that a local MVP does not need: [push notifications](https://developers.google.com/workspace/calendar/api/guides/push).

Build persistent reminder jobs keyed by calendar, event occurrence and reminder offset. Reconcile rescheduled/cancelled events. Handle timezone, recurring occurrences, all-day events, restart and sleep/wake catch-up. An app that is stopped or a laptop that is asleep cannot promise an on-time local alert. Let the user choose lead time and which calendars count. Initial queries: “What is next?”, “What is on today?”, and “What changed since I checked?” Each answer should include the event time and the last successful sync status.

## WhatsApp notification summaries

Use a small native Windows helper with the manifest capability and explicit Windows permission for `UserNotificationListener`. Filter received items to WhatsApp before passing data to Setta. Microsoft's [notification listener documentation](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener) describes the required capability and UI-thread permission request.

This observes notification snippets, not complete chat history. Hidden previews, muted chats and notifications never delivered to Windows create gaps. Keep IDs, timestamps and revision hashes for deduplication; establish an initial baseline so existing notifications are not falsely described as newly received. Permission denial/revocation must show unavailable. Summarizing or dismissing a notification must not imply that a WhatsApp message was read or replied to.

First interaction: “Any new WhatsApp notifications?” Return only unseen collected snippets, their collection interval and an explicit coverage label. Do not add sending or full chat scraping to this slice.

## Desktop work assistance

Prefer service APIs for calendar data, browser DOM for websites, Windows UI Automation for accessible native controls, and screenshot targeting as fallback. See [Microsoft UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiautocore-overview) and [Windows screen capture](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture).

Every action needs fresh target evidence and an observed postcondition. Use one desktop execution lock, bounded steps, cancellation, and a visible stop control. Never classify an accepted input or process launch as successful task completion. Hand elevated/security prompts back to the user rather than weakening Windows protections.

| Reference | What to learn | Adoption decision |
| --- | --- | --- |
| [Microsoft UFO](https://github.com/microsoft/UFO) | Windows application agents and UIA/Win32 integration; current main is UFO³, with UFO² desktop material still present | Study action adapters and verification; avoid replacing the existing companion |
| [UI-TARS Desktop](https://github.com/bytedance/UI-TARS-desktop) | Computer/browser operator loop and task traces | Prototype one bounded task before selecting its runtime |
| [OmniParser](https://github.com/microsoft/OmniParser) | Locating visual controls from screenshots | Optional perception fallback; not a complete agent |
| [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) | Conversation interruption and avatar expression events | Interaction reference; preserve existing mother assets and Sarvam boundary |

These projects document useful components; none establishes reliability or acceptable latency on this laptop without local evaluation. Screen awareness, GUI control, long-term memory and caring conversation remain separate engineering responsibilities.

## Implementation order and acceptance gates

1. Google connection and event cache: actual account sign-in, read-only selected-calendar access, event query, revoked-access recovery, timezone/recurrence and cancelled-event checks.
2. Persistent reminders: exactly one alert per occurrence/offset; edit/delete reconciliation; restart and sleep/wake behavior verified. Preserve muted audio and use visual reminders until explicitly resumed.
3. WhatsApp notification helper: real WhatsApp toast observed on this laptop, baseline/deduplication, hidden-preview and permission-denial handling, bounded summary with no send capability.
4. One desktop workflow: explicitly requested opening of a chosen application/document, fresh target verification, cancellation during execution and honest outcome reporting. Then add a small browser/native workflow with UIA/DOM before generalizing.
5. Combined daily briefing: upcoming events, collected notification snippets and relevant mother-chat commitments, each with provenance and freshness. Quiet hours and interruption timing must be configurable.

Facial context should adjust timing gently: sustained eye closure or possible yawning can suggest a break. Expressions do not reliably prove emotions, intentions or work quality. Do not make inferred sadness, laziness or productivity permanent personal facts.

## Boundary for this research pass

This document is an implementation specification, not an integration claim. No new running calendar/notification service, packaged native helper or end-to-end desktop workflow was produced in this pass. Existing source and connected-calendar availability were inspected; provider/hardware acceptance gates above remain to be executed during implementation.
