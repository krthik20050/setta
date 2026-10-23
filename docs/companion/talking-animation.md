# Talking animation and preferred Malayalam voice

Updated 2026-10-20. The user explicitly preferred the first Malayalam sample on the language-switch review page, displayed reply-to-audio-ready 3.351 seconds. It uses candidate 8 at pace 1.18; these settings remain unchanged. That number is a measurement from one test, not a voice version or a latency guarantee.

## Artwork and runtime

- Approved reference: `assets/mother/artwork/mother-likeness-v6.png`, preserved.
- New generated derivative: `assets/mother/artwork/mother-conversation-v9.png`. Eight full-body drawings: four integrated mouth shapes across two hand poses. It was generated from the approved reference; likeness and motion still need the user's visual judgment.
- Asset SHA256: `58DC5C9B762DD0C11E9C6C83095A9450E5D4EAC3E77D90920A7FBCA76A18DAFC`.
- `src/mother_animation.py` crops the 4x2 sprite grid, uses common scale and foot alignment, and supplies eight `talk` frames. Alpha is made binary for Tk's color-key window, avoiding dark edge fringes. Existing idle/walk/other emotion artwork is preserved.
- `src/speech_motion.py` reads generated 16-bit PCM WAV locally into 50 ms RMS energy bins. Quiet bins close the mouth, louder speech selects different baked mouth shapes, and slower gesture phases select relaxed versus open-palm poses. This is approximate audio-reactive animation, not phoneme-aligned visemes, a 3D facial rig, or semantic hand-gesture generation.
- `src/sarvam_voice.py` sends the envelope and monotonic playback-start timestamp to the UI. Stop and playback completion clear it. Analysis adds no network request and does not change audio bytes, pitch or speed.
- `src/app.py` selects full character frames during speech and no longer draws the old `speaking_mouth` canvas overlay. Spontaneous yawn/hand-wave triggers do not replace the speaking pose during a spoken chunk. Existing native playback and captions remain.
- The idle approved still and generated talking poses are different illustrations; a visible pose/likeness transition is possible. This has not been represented as photo-realistic video animation.

## Pronunciation

The user could not recall specific mispronounced words, so no speculative replacements were added. `config/amma.json` and its example now have an empty `pronunciations` map per language. Add only reviewed errors, for example an acronym's spoken letters, under the corresponding language. Matching is case-sensitive and uses whole-word boundaries; replacements affect TTS input only, not the bubble text or stored reply. Voice routing is selected before applying replacements so a correction does not switch the approved clone.

`src/pronunciation.py` supplies the speech-only replacement layer. Native-language text remains internally available to TTS for pronunciation while the visible Malayalam bubble stays Manglish. `enable_text_normalization=true` is sent to Sarvam for number, date and currency pronunciation. It does not guarantee every name or borrowed word will be correct.

Sarvam's cloned-voice contract documents native/code-mixed text and normalization, but not a `dict_id` field. Its published pronunciation-dictionary examples apply to the separate Bulbul TTS APIs, so the companion does not send that unsupported parameter to cloning. Sources: https://docs.sarvam.ai/api-reference/voice-cloning/clone and https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/pronunciation-dictionary.

## Preview and verification

- Approved audio, unchanged: `assets/mother/voice/experiments/language-switch-latency-2026-10-20/1-ml-IN.wav`.
- Preferred example is recorded in `config/voice.json`.
- Run `python tools/render_talking_preview.py` to create `docs/previews/talking-v9/talking-frames.png`, `talking-preview.gif` and `talking-preview.mp4`. The MP4 reuses the approved audio and the same frame-selection algorithm as the app. It is an offline rendered preview, not a recording of the desktop window.
- Shared browser review files are copied under `assets/mother/voice/experiments/talking-animation-2026-10-20/`, served by the existing loopback voice preview server on port 8768.
- Regression suite: 83 tests pass, including envelope pause handling, different mouth/hand states, unchanged source text after pronunciation replacement, eight distinct baked poses, transparent edges, common foot baseline and existing voice lifecycle checks.
- Real microphone-to-speaker animation timing and subjective likeness require the user's review. Playback timing is tied to the Windows audio handoff; hardware output latency is not measured.
