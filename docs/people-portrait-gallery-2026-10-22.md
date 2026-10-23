# People gallery: photo-first portraits

Date: 22 October 2026
Reference: owner-provided IMG_4341.PNG People view. It is a layout reference, not a source of identities to enroll.

## Changes
- Three-column gallery of tall, rounded real-photo tiles, with white names over a shaded bottom edge, matching the requested photo-first hierarchy.
- Sample counts and recognition/removal controls appear only in Edit people mode. Clicking the portrait changes its display photo.
- Add photo chooses and persists a portrait immediately via Pillow; it does not run DeepFace, add an embedding, or wait for a perfect face detection. Images are limited to JPG/PNG/WebP under 20 MB and 25 megapixels; EXIF orientation is applied, metadata is excluded from the saved JPEG.
- Selecting a cover is independent of adding recognition samples. Edit > Enroll retains the prior explicit enrollment flow.
- Missing display images can be backfilled while Camera is on, after three clear repeated known matches separated by at least a second. Gates require a crop >=80px, brightness/sharpness checks, cosine >=0.85 and a >=0.12 margin to the next identity. Unknown and ambiguous matches do not get portraits. Existing portraits are never overwritten by this backfill, and recognition samples are not changed.
- Camera-off prevents new portrait capture. The user previously requested saving known appearances; this backfill is limited to a missing thumbnail for an already enrolled name. Optional sample-learning candidates still require explicit review before updating embeddings.

## Data limitation
The current legacy known_faces entries contained NumPy face encodings and no JPEG reference photos. The application cannot reconstruct an original face image from an embedding. Those entries show Add photo until the owner assigns a portrait or a sufficiently clear repeated camera match fills it. The reference screenshot's people are not silently enrolled or copied into the owner's saved identities.

## Code
- src/people_portrait.py: cover cropping, rounded corners and readable name overlay.
- src/modern_hub.py: image-first tiles, edit mode and asynchronous photo chooser/save flow.
- src/face_id.py: independent set_portrait API and camera-gated missing-preview capture.
- tests/test_face_gallery.py: portrait persistence without embedding mutation, tile dimensions/alpha, backfill gates and ambiguous-match rejection.

## Verification boundaries
Full suite and real-widget hub smoke run for this change; final results are appended below. Camera backfill uses deterministic synthetic frames in tests. No claim that all legacy entries already have images or that live identity accuracy is calibrated. Portrait assignment is user-labelled; the cover photo is not additional identity evidence.

Final verification: 183 tests passed. Expanded hub smoke passed, including choose-portrait, image refresh, unchanged sample count, and photo-tile rendering.
