# Side-Eye source audit and Setta integration plan

Reviewed 2026-10-20. Upstream revision: 5d27d6a1935e3c14bb618a14d12f56c9ce3750b8.
Boundary: source inspection plus synthetic execution of the real ScreenContext classifier. The macOS desktop observer and Sarvam providers were not run here. Setta remains running with audio disabled; this audit does not change application behaviour.

## What actually supplies desktop context
- screen.py:104 _front_app runs lsappinfo front, then queries application display name and bundle ID. This is app metadata, not pixel analysis.
- screen.py:35-58 AppleScript reads the active tab title and URL of every non-minimized Chrome/Safari window, only if that browser is already running. It does not read every inactive tab or browsing history. A non-minimized window can still be occluded; this is not proof of screen visibility.
- screen.py:120 _browser_tab extracts normalized domains, prioritizes a distraction, marks other windows background=True. get_screen_context also checks running browsers when the foreground app is different.
- screen.py:155 ScreenWatcher polls at one second by default. A monotonic distraction timer runs only for a focused distraction, not merely a background window.
- idle.py:14 get_idle_seconds runs ioreg -c IOHIDSystem -d 4, extracts HIDIdleTime, converts nanoseconds to seconds. Failures return zero, so unavailable idle telemetry is conflated with recent activity. Polling is normally 1 second and speeds to 0.25 seconds during an interruption.
- No screenshot or webcam input appears in the reviewed desktop-context/brain path. Browser access is macOS AppleScript Automation; this cannot be copied unchanged to Windows.

## What supplies the apparent intelligence
- screen.py:19-76 uses hardcoded site/app lists, plus study-related words in YouTube titles. Unlisted apps are not flagged; this does not verify productive work.
- brain.py:268 _on_idle rejects mouse/keyboard activity as a return-to-work signal when the focused app is classified distracting. Otherwise activity can interrupt a reminder.
- brain.py:304 _work_until_idle triggers on idle or focused-distraction duration. config.py real mode uses 420 seconds idle and 90 seconds focused distraction; demo uses 8 seconds for both.
- brain.py:339 _converse runs reminder -> listen -> interpret -> snooze/escalate/return. The mic is opened after speech, with 150 ms speaker-tail delay.
- brain.py:409 _understand sends spoken words, app/domain/title, reminder level, prior excuse and streak to Sarvam. JSON intent categories are EXCUSE, CONFESS, BACK_TO_WORK, CAUGHT_LYING and UNCLEAR. These labels are inferences, not lie detection.
- Guardrails downgrade unsupported accusations and treat apologies as confession. A local keyword classifier/line bank takes over on timeout or malformed output. The fallback can still classify an excuse as lying solely because a distraction is present.
- sarvam_client.py:123 requests JSON; config.py sets a four-second LLM timeout. Voice uses streaming TTS and cached common lines. Its advertised latency has not been verified here.

## Synthetic checks against actual upstream classifier
YouTube entertainment -> distracting; YouTube Python tutorial -> exempt; research on Reddit -> distracting; entertainment title containing tutorial -> exempt; unknown app -> not flagged. These demonstrate brittle metadata rules, not measured real-world accuracy.

## Setta gaps confirmed from current source
face_id.py stores one embedding per name, uses default DeepFace representation on an already-cropped unaligned face, and a fixed cosine threshold of 0.4. Enrollment overwrites the same name. No multi-view templates, quality gate or threshold calibration. Recognition occurs every 30 detected-face frames rather than a wall-clock schedule; late identity results are not tied to a track generation. Errors can be swallowed. Webcam mood labels come from a few blendshape thresholds; these are facial movements rather than verified emotions. face_activity.py has a temporal mouth-opening heuristic and prolonged-eye-closure observation, not a validated yawn/sleep classifier. Setta has no desktop-context observer yet.

## Windows integration to build
1. Foreground process/window via GetForegroundWindow, GetWindowTextW and process identity; idle time via GetLastInputInfo. Keep unavailable as unknown, not zero. Ignore Setta's own popup/character window so interacting with mother does not count as changing task.
2. Optional Chrome/Edge extension sends active tab title/domain and visibility/focus changes over an authenticated local bridge. Continuous metadata needs explicit tabs/host permission; activeTab alone is temporary and user-invoked. Window titles alone do not give reliable domain identity. Exclude private windows by default and strip query strings.
3. Timestamped local ContextSnapshot: user identity/confidence, face present, quality, eyes-closed duration, possible-yawn event, head direction, foreground app, domain/title if permitted, idle duration, current goal, confidence and source per observation. Never retain passwords, raw key content or continuous video as part of this observer.
4. Goal-aware policy produces work/leisure/unknown and selects quiet/check-in/encourage/break. Cooldowns and user correction override repeated nagging. Laya can evaluate structured text snapshots; it cannot replace the vision models. Begin with a deterministic baseline and compare decisions on labelled scenarios.
5. Optional one-shot screenshot understanding when requested or explicitly enabled, with visible pause/exclusion controls. Metadata observation and screenshot vision are distinct capabilities.

## Face improvements in priority order
A. Guided multi-angle enrollment with sharpness/light/face-size gates, aligned crops, explicit model ID and version per embedding, multiple templates, safe replace/delete flow.
B. Track identity with consecutive matches, calibrated threshold plus runner-up margin, unknown on low quality or loss; discard results from expired tracks. Compute recognition in a separate rate-limited worker.
C. Temporal behaviour: baseline blink/eye closure, jaw trajectory, head pose; label yawning/talking/laughing/singing clips and report false alarms per hour. Do not infer sleep or intent from one cue.
D. Benchmark OpenFace 3.0 gaze/action-unit analysis against existing MediaPipe, measuring CPU latency and accuracy on this camera. Optional anti-spoofing is separate and does not make webcam identity suitable for security authentication.
E. Combine task context and camera observations only after each independently works. For example a lecture + low keyboard activity is compatible with studying; eyes closed briefly is a blink, not proof of sleeping.

## Sources
https://github.com/garimapahwa/side-eye/blob/5d27d6a1935e3c14bb618a14d12f56c9ce3750b8/screen.py
https://github.com/garimapahwa/side-eye/blob/5d27d6a1935e3c14bb618a14d12f56c9ce3750b8/idle.py
https://github.com/garimapahwa/side-eye/blob/5d27d6a1935e3c14bb618a14d12f56c9ce3750b8/brain.py
https://github.com/garimapahwa/side-eye/blob/5d27d6a1935e3c14bb618a14d12f56c9ce3750b8/config.py
https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getforegroundwindow
https://developer.chrome.com/docs/extensions/reference/api/tabs
https://developer.chrome.com/docs/extensions/develop/concepts/activeTab
https://github.com/CMU-MultiComp-Lab/OpenFace-3.0
