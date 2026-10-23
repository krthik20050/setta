# Mother companion: implementation and research, 2026-10-20

## Architecture
Camera -> quality / landmarks / identity -> timestamped observations -> temporal event detector -> decision policy -> dialogue / voice / sprite.
The decision model consumes observations, not raw webcam pixels. Unknown or poor-quality observations must remain unknown. Never derive character, mental health or actual intent from facial appearance.

## Reusable components
- MediaPipe Face Landmarker: local landmarks, blink and jaw blendshapes. Already installed. https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python
- Laya: open decision engine with typed choice, yes/no and score questions. Candidate policy model; evaluate on labelled Setta scenarios before enabling automatic interventions. It does not replace a vision model or dialogue generator. https://github.com/NandhaKishorM/laya
- jevos: alternative local Jev-compatible decision engine, including Windows CPU release. Candidate baseline. Published latency is not verified on this machine. https://github.com/feder-cr/jev
- YawDD+: research dataset with frame-level yawn annotations. Useful for evaluating a trained video classifier; paper metrics are not evidence of performance on this webcam. https://arxiv.org/abs/2512.11446
- OpenCV YuNet + SFace: candidate lightweight identity stack to benchmark against existing DeepFace. Check individual model licenses and quality before replacing saved embeddings. https://github.com/opencv/opencv_zoo
- InsightFace: recognition candidate, but pretrained models carry non-commercial research restrictions by default. https://github.com/deepinsight/insightface
- Sarvam: candidate Indian-language STT/TTS and conversation provider. Needs configured credentials and measured speech quality/latency. https://docs.sarvam.ai/api/getting-started/models
- Side-Eye: reference for reminder, reply, snooze and follow-up state machine; its desktop observer is macOS-specific. https://github.com/garimapahwa/side-eye

## Implemented first slice
Removed random idle actions; right-click and dragging cancel walking; menu grab releases correctly; walk stays within horizontal screen bounds. Brief mouth opening no longer plays audio. Possible yawn requires sustained jaw opening, closing and cooldown. Added prolonged-eye-closure observation and face-observation menu. Enrollment uses a fresh detected face crop from the existing camera in a background worker, with the same BGR crop convention used for recognition. This remains single-sample enrollment, not calibrated multi-view enrollment. Existing embeddings are preserved and may need re-enrollment.

## Next vertical slices
1. Guided multi-view enrollment, quality gates, per-person templates, match threshold calibration and an unknown identity state. Do not silently overwrite enrolled identities.
2. Labelled yawning / speaking / laughing / singing / deliberate mouth-opening clips across lighting and glasses. Train or evaluate a temporal classifier. Initial duration heuristic cannot reliably separate all these behaviours.
3. Explainable policy with cooldown, pause, unknown handling; compare deterministic baseline, Laya and jevos on identical labelled scenarios.
4. Windows active app and idle context; optional screenshot analysis with visible capture state and app exclusions. Do not send raw video continuously to cloud providers.
5. Mother photo -> consistent transparent pixel character reference -> idle, blink, talking, loving, proud, concerned and scolding frames. Verify consistent dimensions, alpha, pose alignment and playback in-app. Photo is pending.
6. Sarvam speech round trip with interruption, microphone state, fallback lines, language choice and personality phrases.

## Verification boundary
Five deterministic temporal-cue regression checks pass. This does not validate real yawn recognition, drowsiness accuracy, multi-person identity accuracy, Sarvam integration or Laya inference. Actual user identity must be enrolled by the user in the guided UI, not guessed from whoever happens to be on camera.
