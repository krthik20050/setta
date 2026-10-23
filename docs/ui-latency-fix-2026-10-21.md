# UI latency diagnosis and fix

## Reproduction

`python tools/measure_ui_latency.py --check` builds the real six-page CustomTkinter hub with synthetic conversation data and no camera/provider calls. It loads 80 messages, holds the same SQLite chat database with an exclusive background write for 650 ms, and measures Tk heartbeat gaps while requesting history. It also measures page switching. The check fails if the maximum heartbeat gap exceeds 200 ms.

Before the fix, the isolated run measured 388.5 ms entering conversation and a 664.3 ms heartbeat gap while storage was busy. This reproduces a main-thread freeze; it does not establish that every delay on the user's laptop had this cause.

Ranked hypotheses: synchronous storage on the UI thread; full transcript redraw per individual message; unnecessary avatar and status repaint. The storage-lock test directly isolated the first. Source inspection also found that loading 80 messages rendered the growing transcript 80 times.

## Changes

- A bounded serial storage worker handles chat/reminder reads, reminder changes, preference writes, memory export and saved face embeddings. Tk drains completion results without waiting for work.
- Page changes use cached state and request fresh data asynchronously. History renders once per changed batch, preserving the original text and display-script choice.
- Reminder scheduling no longer queries SQLite from the Tk housekeeping callback. Pending reminder changes show a saving state and block conflicting button actions.
- Preference writes coalesce to the newest snapshot. Actual quit waits asynchronously for queued writes as well as camera cleanup.
- Avatar and status widgets update only when their values change. Cached animation frames remain in use.
- Worker queues are bounded and requests with the same key are deduplicated. UI completion callbacks run on the Tk thread, including errors.

## Evidence

Repeated isolated runs after the fix measured 32-43 ms maximum heartbeat gaps. The final run measured 43.2 ms maximum heartbeat gap, 23.2 ms maximum page switch and 24.1 ms chat navigation. Chat navigation returns while history loads in the background, so the navigation measurement is not total database-load completion time. All 114 regression tests passed, and the updated application was restarted.

The native widget smoke check covers six pages, asynchronous reminder save/snooze/pause, latest visibility persistence, Manglish/native display, inline face validation, serial typed submission and mute preservation. Worker tests cover thread ownership, slow I/O, bounded/deduplicated requests, failure recovery and queued writes at shutdown.

These are source/native-widget and synthetic storage-contention measurements, not a guarantee of all hardware, model or network latency. Recognition/model inference and remote reply generation retain their own latency. No user conversations or frames are included in the performance fixture.
