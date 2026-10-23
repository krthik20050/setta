# Real People discovery: capture, label, recognize

Date: 22 October 2026
Supersedes the screenshot-copy album described in reference-people-recreation-2026-10-22.md.

## Correct product requirement
The reference image described a People gallery layout, not content to seed into the app. The earlier implementation incorrectly copied named faces from the screenshot. That display album has been disconnected from FaceID and moved from data/people_album to runtime/retired-reference-people-2026-10-22. The source screenshot and original enrolled embeddings remain unchanged. No screenshot portrait is used for recognition.

## Implemented workflow
1. Open Camera and turn it on. Collect unfamiliar faces to label is visible and can be disabled; it only runs while Camera is on.
2. Clear detected faces are represented by the existing local face model. If not recognized, a local cropped photo and its embedding are saved to the unlabelled inbox.
3. The actual photo appears in People with a Who is this field, Save name and Discard.
4. Saving a new name creates a real enrolled identity with that photo and embedding. Entering an existing name adds a confirmed reference sample to it, retaining the existing five-sample bound. Names with spaces are normalized to underscores for existing storage compatibility; tile labels display spaces.
5. New appearances match against saved references. Other uncertain appearances remain reviewable; the app does not assign a permanent label from a guess.

## Camera and People screen

The Camera page presents the live preview beside one Add a person panel. A shared name field works for both a fresh camera face and a selected or dropped photo, so an imported photo can be turned into a recognition reference without a separate window. The preview remains off until the user starts the camera.

The People Setta knows gallery uses small circular crops, names and sample counts in a compact left-aligned grid. Unlabelled captures remain real crops with inline name, save and discard controls. A review banner takes the user to the pending face field. Selecting a saved person fills the name field so the next camera or photo sample can be added to that identity; Edit people reveals add-photo and removal controls. Recognition settings keep discovery and repeat-sample review separate, with their local-storage and approval behavior explained beside the controls.

The visual direction follows the user-approved Setta concept. Sample portraits in that concept are not app data; the live gallery reads only saved face previews and camera captures.

The existing review mechanism for additional known-person samples remains available. This grows the local reference set, not the neural network's trained weights. User labelling is the source of identity truth.

## Storage and boundaries
- data/known_faces/unlabelled holds up to 12 pending crops and embeddings. Duplicate pending captures are grouped by embedding similarity; a three-second insertion cooldown prevents rapid filling. Pending data survives restart.
- Rejects crops below 80px, poor brightness, blurry faces, nonfinite or zero embeddings. Similarity grouping is a heuristic and is not a measured accuracy claim.
- Discard removes an unlabelled capture. An unsuccessful label leaves it intact. Enrollment and disk writes run off the UI thread.
- Camera-off or disabling collection stops new discovery. Detection is required; raw desktop frames and bystanders outside the detected crop are not saved by this flow.
- Existing saved names with no original image cannot reconstruct it from an embedding. A new captured/confirmed reference supplies the picture. No copied screenshot face fills that gap.

## Code and validation
src/face_inbox.py owns bounded capture persistence, duplicate grouping, labelling and discard. src/face_id.py now analyzes faces even when no identities are enrolled and routes unknown faces to the inbox only when discovery is enabled. src/modern_hub.py exposes the real photo/name/review flow. Hub preferences persist collection choice.

Tests cover actual embedding/crop persistence, label-to-enrollment, recognition after restart, duplicate grouping, adding a sample to an existing person, failed-label recovery, discard, quality gates and queue capacity. The real-widget hub smoke exercises an unlabelled tile through Save name into a known tile. These use synthetic images/embeddings, not a verified live-human recognition benchmark.

Earlier face-discovery baseline: 189 full-suite tests, the expanded hub smoke, and five focused discovery tests passed before this screen redesign. For the current UI revision, Python syntax compilation passed. I could not run the widget smoke or gallery tests in the active `C:\Python313` environment because it lacks `customtkinter`, `numpy`, and Pillow; no project `.venv` is present. The updated screen therefore still needs a runtime check in the app's fully installed environment.
