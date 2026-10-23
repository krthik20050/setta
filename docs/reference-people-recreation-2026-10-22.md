> Superseded: the copied reference album is no longer part of the live gallery. See real-people-discovery-2026-10-22.md.

# Screenshot-matched People gallery

Date: 22 October 2026

The owner explicitly requested use of the supplied people's photos and recreation of IMG_4341.PNG. Applied REA visual-reference routing and redesign-existing-projects; implemented using the existing native Python UI.

The People section now has a near-black background, three columns of rounded portrait tiles, white names over the lower edge, adaptive tile size, and a compact Edit people control. Default browsing hides sample counts and recognition actions. Seven labelled portraits were extracted locally from the supplied screenshot (Karthik, Gokul N R, Athira k jayan, Jeswin, Kamal, NiviN, Dheeraj). Unlabelled faces were not assigned guessed identities. Cropped reference photos are stored under data/people_album with a names manifest; the original file is unchanged.

Display portraits are separate from biometric embeddings. Reference-only people appear in the gallery but remain unenrolled; Edit people explains this. A matching existing saved name uses its current recognition samples and a reference display portrait only when it lacks a cover photo. Existing embeddings were not replaced or newly calculated from the screenshot. This is a name-label association provided by the owner, not a claim that the app verified who each pictured person is.

Portrait changes and deletion remain local and asynchronous. Portrait-only deletion does not remove another person's enrollment; removing a merged enrolled entry removes both its display reference and its own enrollment. A test confirms that importing reference portraits alone leaves the recognition dictionary empty.

Validation: 183 full regression tests passed before the final display-name adjustment; seven focused gallery tests then passed, including the new reference-only test. Expanded native-widget hub smoke passed. Source screenshot crops are deliberate local reference-asset extraction, not newly generated or altered facial identities.

Files: src/people_album.py, src/face_id.py, src/modern_hub.py, data/people_album/, tests/test_face_gallery.py.

Runtime check caught and fixed an odd-height gradient-rendering error. Added an odd-height regression test; all eight gallery tests passed. All seven supplied portraits rendered at the previously failing size.

Generated runtime/people-gallery-preview.png using the same portrait renderer and actual supplied photo album. Final native Camera click was interrupted by user input; no further UI actions were taken.
