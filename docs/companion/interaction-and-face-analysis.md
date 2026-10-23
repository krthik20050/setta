# Interaction and facial-analysis review — 2026-10-20

## Implemented interaction changes
The sprite remains small for quiet walking. A separate 224-pixel portrait uses the original high-resolution approved expression artwork; dialogue sits underneath. No speech graphics cover the sprite or portrait. Right-click groups common actions first: face view, walking/stay, talk, expressions, camera/recognition, sound. Hiding the face view is reversible; new dialogue reopens it. Existing recognition and voice handlers remain connected.

## UX research and rationale
Microsoft Windows guidance recommends meaningful inline labels and choosing richer interactive surfaces when a tooltip is insufficient. A conversation should remain readable and should not obscure the character it relates to. Group settings by user goal, keep frequent actions near the top, and keep camera enrollment separate from visual character expressions.
Sources:
https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/tooltips
https://learn.microsoft.com/en-us/windows/apps/design/basics/

## Advanced camera research: recommended sequence
1. Improve input quality and enrollment first: one tracked face, adequate size/light/sharpness, multi-view samples, unknown identity on poor match, measured false acceptance/rejection, identity expiry after tracking loss. Existing enrollment is single sample, not yet this guided flow.
2. MediaPipe facial transformation matrices can supply head pose; blendshapes supply jaw/eyelid/expression movement. Calibrate a personal baseline; keep observation timestamps and confidence. Blendshapes are not identity embeddings.
https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python
https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf
3. Evaluate OpenFace 3.0 for gaze and facial action units alongside the current pipeline. It offers facial behavior analysis, not proof of the user's feelings or intent. Benchmark CPU latency, Windows compatibility, model license, and actual webcam quality before adding it.
https://github.com/CMU-MultiComp-Lab/OpenFace-3.0
https://arxiv.org/abs/2506.02891
4. Evaluate a temporal yawn classifier using clips labelled talking, singing, laughing, yawning and ordinary mouth opening; report precision/recall and false alarms per hour. Current duration heuristic remains provisional.
https://arxiv.org/abs/2512.11446
5. Evaluate optional anti-spoofing separately; MiniFASNet ONNX is a candidate, not a guarantee of liveness or secure authentication. Test printed photos and screen replays.
https://github.com/yakhyo/face-anti-spoofing
6. Feed time-windowed observations and desktop task context to the decision engine. Use explicit uncertainty and cooldowns. Never treat face geometry as proof of laziness, sadness or concentration. Pause controls and excluded desktop applications remain requirements for future screen capture.

These are researched candidates. OpenFace, anti-spoofing, multi-view enrollment and learned temporal yawn detection have not been installed or validated in Setta.
