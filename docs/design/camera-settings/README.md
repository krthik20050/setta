# Approved Camera and Settings redesign

Date: 21 October 2026
Status: Implemented in source; approved concept images retained alongside this document.

## User decision
The owner approved the generated Camera and Settings previews and requested implementation with documentation. The previews are design references, not records of enrolled people. Original mother artwork is unchanged.

## Design references
- [Camera concept](approved-camera-concept.png)
- [Settings concept](approved-settings-concept.png)
Generated with the built-in image generation tool. Prompt direction: warm off-white and forest green native desktop UI, quiet typography, left navigation, camera-off preview beside photo drop target, saved-person gallery and enrollment progress; Settings with individual Light/Dark/System thumbnail choices, simple preference rows and a personality column. No generated family portraits are enrolled or used as actual references.

## Camera behavior
- The camera stays off until requested and stops when leaving Camera, as before.
- Add a clear single-person JPG, PNG or WebP using Choose photo or native file drop. Image size limits and the existing one-face/face-size checks apply.
- A drop before entering a name is staged locally; enter a valid name and choose Save selected photo. A photo is not enrolled before a name is provided.
- Enrollment uses a genuine indeterminate progress bar during model preparation and disk writing. It shows full completion only after saving, or resets on error. No fabricated percentage.
- Saved people are loaded on a background worker. New references include a small local JPEG preview cropped to the detected face, alongside existing NumPy embeddings. Older embeddings show an initial until updated; no likeness is fabricated.
- Update selects the existing name and adds a fresh sample, retaining at most five samples. Remove requires an inline confirmation and removes that person's embedding file and local preview. This does not delete original photos selected from elsewhere.
- Names retain existing validation: up to 60 letters/numbers/hyphens/underscores. No spaces yet.
- Face processing stays local. Model installation may require its existing model download; enrollment is not cloud recognition.

## Settings behavior
- Individual code-rendered Light, Dark and System previews replace the joined segmented theme control. Selection has a thin accent outline.
- Language selection uses a dropdown. Manglish/native script behavior and voice pronunciation are preserved.
- Personality is placed beside preferences, with backup/import retained. Long content scrolls on smaller windows.
- Preferences and face file operations continue through bounded background I/O, preserving navigation responsiveness.

## Files and dependencies
- src/modern_hub.py: Camera gallery, progress, drop target and updated Settings layout.
- src/face_id.py: preview persistence, list/remove APIs and photo sample extraction.
- requirements.txt: tkinterdnd2>=0.4,<0.5 (installed 0.4.4.1 in this environment).
- tests/test_face_gallery.py: restart persistence, legacy compatibility and path validation.
- tools/verify_hub.py: real-widget isolated enrollment/drop-handler/success/failure/gallery/theme checks.

## Verification
- Full suite: Final full suite: 161 tests passed, including the staged-drop refinement; affected UI smoke also passed.
- Hub smoke: native tkdnd loads, a path containing spaces reaches the drop handler, synthetic face data saves a thumbnail, progress completes, failures reset and controls recover; six-page navigation remains functional. Recognition is mocked here, not a hardware/model accuracy measurement.
- UI latency fixture: maximum page switch 91.8 ms, heartbeat gap 32.4 ms under simulated storage contention.
- Running Windows app: Settings and Camera inspected. The desktop avatar can overlap the hub; this is existing separate overlay behavior.
- Physical Explorer-to-app drag, live face-model accuracy and packaged dependency inclusion remain unverified. The actual drop target and its handler are wired; no claim of physical drag testing.

## Recovery
If native drag-and-drop cannot initialize, Choose photo remains usable and the UI removes the drop instruction. Failed enrollment restores controls. Face-list reads and updates are coalesced to avoid stale gallery results after writes.
