# Compact controls, familiar faces and conversation improvements

Date: 21 October 2026

## Stack verified from source
This is a Python desktop application, not Electron. Tkinter supplies the window/event loop; CustomTkinter supplies the hub controls. Pillow renders artwork and face previews, OpenCV handles camera frames, MediaPipe handles face/activity cues, and DeepFace produces identity embeddings. SQLite stores local conversation/reminder data. Sarvam supplies the existing language/voice integration; that integration is not changed in this iteration. The existing local hands-free server/browser surface is separate from the native hub. tkinterdnd2 provides photo file drops.

## Changes and rationale
- Appearance now occupies one short row with a sun/moon switch plus a small Follow system control. System preference disables manual switching until deselected. No large thumbnail theme cards.
- Saved faces are placed above the Camera controls so identities are easier to find. Previews are larger (88px). Existing embedding-only identities explicitly show Photo missing and Update; embeddings cannot be converted back into the original photo.
- Repeat-appearance collection is opt-in and local, and runs only while the Camera page's camera is on. No unknown-person archive or continuous video recording.
- New candidate photos are shown with Yes, same person and Dismiss. Approval adds the embedding to that person's existing bounded sample set and supplies a preview; dismissal leaves identity embeddings unchanged. This refines reference matching; it does not retrain DeepFace's neural network.
- Conversation has clearer role colors, spacing and indentation, draft prompt shortcuts, and Copy last reply. Shortcuts only draft text and do not send it. Existing memory, Manglish display, provider ownership and serial-send guard are retained.
- Reminders opens with the general named-habit flow. The older large water setup is collapsed behind Water quick setup; presets, interval wheel, quiet hours and history remain available.

## Candidate collection policy
Local heuristic gates: known identity only, cosine similarity at least 0.80, separation from next identity at least 0.12, crop at least 80px each side, reasonable mean brightness, Laplacian sharpness >=40. Three qualifying matches at least one second apart within 15 seconds; one pending candidate per person and ten-minute in-process collection cooldown. These thresholds are conservative starting values, not calibrated accuracy claims. Camera-off and disabling collection stop new collection; existing candidates stay available to review. Pending candidates live in the face directory's candidates subfolder; removing a person also removes their candidate.

## Research references
- Official CustomTkinter switch component: https://customtkinter.tomschimansky.com/documentation/widgets/switch/
- Google Photos face groups: named groups and correcting wrong labels informed review-before-approval: https://support.google.com/photos/answer/6128838?hl=en-en

## Validation and limits
165 full tests passed, including candidate opt-in, quality/ambiguity rejection, manual approval, dismissal and deletion. Isolated real-widget smoke covers theme switching/system state, conversation drafting, camera-off collection guard and prior navigation/enrollment/reminder flows. Controlled latency check: max page-switch 233 ms; max heartbeat gap 32.7 ms during simulated storage contention. Not a provider or hardware latency guarantee.
Actual family recognition accuracy, live candidate collection and physical File Explorer drag/drop require device testing and are not claimed verified here. Older identities require a fresh photo/camera sample to show a thumbnail.
