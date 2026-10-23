# Google Photos People & pets: product research for Setta

Date: 22 October 2026

## What Google documents

Google Photos presents face groups as a private, opt-in way to browse and search photos. Its official help describes a three-stage flow: detect faces in photos, produce numerical face models that estimate similarity, and group images that are likely to show the same person. Google says other visible context can also affect group membership, including photos taken close together or matching clothes when a face is not visible. Its help does not publish the production model, thresholds, training data, or full implementation, so those details remain unknown.

People & pets is a gallery of groups, not a gallery of manually supplied reference headshots. A user opens a group, adds a name or nickname, and can later merge duplicate groups, respond Same / Different / Not sure to a merge suggestion, change or remove a label, remove a mistaken photo from a group, and choose the group's feature photo. Removing an item from a group does not delete the photo. Google says groups and labels are private to the account and are removed, along with face models, when face grouping is disabled. Google also notes that face models may count as biometric data in some jurisdictions. The feature is not available in all regions or account types.

Sources: [Set up and manage face groups](https://support.google.com/photos/answer/6128838?hl=en), [Face Groups retention policy](https://support.google.com/photos/answer/11965565?hl=en), and [Google Photos privacy and safety](https://safety.google/products/photos/).

## Product lessons for Setta

1. Show a useful face thumbnail first, with a human name underneath. The gallery represents real detected people, not a mock dataset or the source photo used to design the UI.
2. Keep discovery and identity assignment separate. Detection can suggest a group; only the user supplies the identity. Never silently turn an uncertain match into a permanent name.
3. Make correction a first-class action. Setta should let the user say “same person,” “different person,” or “not sure,” move a capture to another identity, remove a capture from the identity, and rename an identity.
4. Keep every correction reversible where possible. Removing a face capture from an identity should preserve the source image unless the owner separately deletes it. A merge should show the groups being combined and offer undo.
5. Show system state plainly: camera is off/on, discovery is paused/on, candidate is waiting for a name, an identity has N saved samples, and a capture was rejected for blur or size. A blank gallery should explain how to create the first real group.
6. Put privacy controls beside the feature: pause collection, clear unlabelled captures, delete an identity and its face data, and explain which data stays on this laptop.

## What is already in Setta

`src/face_id.py` detects and compares live camera face embeddings against locally enrolled people. It uses the strongest cosine similarity per identity, with a fixed match threshold of 0.40 and a 0.06 gap over the next identity; this is a heuristic, not a measured accuracy guarantee. Uncertain matches remain `Unknown`.

When camera discovery is enabled, a sufficiently large, bright, sharp unknown face can enter `src/face_inbox.py`. The inbox stores a cropped image plus its embedding locally, allows up to 12 pending captures, applies a three-second capture delay, and de-duplicates highly similar pending captures. Camera discovery is controlled by a setting and is only used in the camera flow. The People gallery renders these real saved crops with a name field, Save name, and Discard. Saving creates an enrolled identity; entering an existing name adds a reference sample, with a five-sample cap. The app can also ask the owner to review additional known-person samples.

This is a live-camera identity enrollment flow. It is not a Google Photos-style scan of an existing image library: Setta currently has no photo timeline, no all-day background scan, no persistent photo-to-person assignment index, and no merge/correction workflow for already grouped captures. Each enrolled identity stores face embeddings and an optional display crop. The feature does not fine-tune a neural network; it compares future face embeddings against the user's saved examples.

## Recommended build order

### 1. People gallery and identity details

Use one tile per enrolled identity, with a real face thumbnail, chosen name, sample count, and last-seen/capture status only when that timestamp is actually recorded. Selecting a tile should open its saved samples and identity actions. Use an explanatory empty state and distinguish saved people from unlabelled captures.

### 2. Review queue with explicit correction

Keep unknown captures as reviewable items. Add a “same person as…” action to attach a capture to an existing identity, a “different person” action that keeps it separate, and “not sure” / discard. Ask for confirmation before combining identities and make undo possible. Do not auto-merge on the current 0.82 pending-image heuristic; first validate the threshold against consented, representative data.

### 3. Better reference management

Show every sample in an identity and let the owner remove a bad sample without deleting the rest of that identity. Keep the best clear crop as the tile cover and let the owner choose a different cover. When an identity has no sample image, show an honest placeholder and let the owner capture or import an image; embeddings cannot recreate the original photo.

### 4. Quality and accuracy work

Record detection quality and match score for local review. Build a small consented evaluation set with different lighting, camera angles, distance, glasses, and multiple people in frame. Measure false accepts, false rejects, and unknown rates before changing thresholds. Add temporal confirmation for live identification and prefer returning “I’m not sure” to naming the wrong person. Keep age, gender, emotion, or intent claims out of identity matching; those are separate, uncertain classifiers and are not required for a People gallery.

### 5. Privacy and reliability

Add a visible collection status, pause control, one-click clear for pending faces, per-person deletion, and a complete local face-data reset. Persist an explicit model/version record so a future recognition model change can rebuild embeddings from consented images or clearly ask the owner to re-enroll. Verify that deletion covers queued captures, candidate samples, previews, embeddings, and any future indexes.

## REA boundary and confidence

The REA boundary is important here: no authenticated Google Photos account, Google Photos app binary, or authorized People & pets session was available to inspect. So this is a product-behavior study from Google's official help and privacy pages, not a REA trace of Google's private app code. The internal model architecture and operating thresholds are explicitly unknown. The Setta description comes from this repository's source; the proposed features are design recommendations, not observed Google implementation details.
