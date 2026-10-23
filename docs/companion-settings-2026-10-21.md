# Companion controls

- Water interval: plus/minus buttons, Up/Down keys and mouse wheel over the number. Range is 1–1440 minutes. Use Save water reminder to apply the edited interval.
- Camera: off on startup. Turn camera on from Camera; turn it off with the same control, leave the Camera page, or hide the app window. The existing capture owner closes native resources; rapid restart waits for that owner to stop. Preview uses a fresh full camera frame; enrollment still uses a detected face crop. Stop clears cached frames and visible-activity context. An in-flight detector may finish before its owner releases resources.
- Appearance: Light, Dark and System options apply to the existing app and persist across restart. Existing navigation host isolation remains intact.
- Amma profile: Settings edits name, role and custom speaking/behavior instructions. Save merges only these fields into config/amma.json atomically, preserving voice, pronunciations, context, greetings and other existing keys. Existing conversation profiles refresh instructions for the next turn, not an already-generated reply. No source-code rewriting or dynamic code execution is used.

Validation: 134 regression tests passed, followed by targeted camera/profile tests after a stale-result guard. The six-page native-widget smoke covers an actual mouse-wheel event on the numeric entry, themes, no camera request at startup, camera-off on navigation, profile save/reload with isolated data, plus existing reminder/chat/navigation checks. Lifecycle tests use a simulated capture owner; this is not a new live-device enrollment or provider conversation validation. The storage-contention check remained below its 200 ms heartbeat threshold (32.6 ms in the full-check run).

Useful follow-on features: quiet hours, multiple named reminders, a reminder activity history, and profile export/import. These are suggestions rather than implemented capabilities.
