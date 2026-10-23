# Amma: identity, speech style, memory and recognition greeting

## Greeting pronunciation correction, 2026-10-20

The familiar Manglish greeting now resolves to fixed internal speech text identical to the earlier `amma-profile-2026-10-20` greeting. It bypasses reply-model rewriting. This avoids introducing new wording or mixed-language routing into a fixed opening line. Custom edited greetings still use the existing conversion path; changing the greeting does not silently keep the old words.

`src/greeting_speech.py` holds this mapping and caches the generated greeting under `runtime/greeting-cache/`. The cache key includes speech text, language, voice ID, delivery settings and pronunciation corrections, so changed settings regenerate the greeting. Original voice reference 8 and current pace 1.18 remain. The cache contains only this fixed greeting, not arbitrary user conversation audio.

The new cached audio is also saved as `assets/mother/voice/experiments/greeting-pronunciation-2026-10-20/fixed-greeting.wav`, beside an unchanged copy of the earlier greeting and `listen.html` for comparison. `results.json` records the chosen reference, pace and checksum. The earlier audio is not labeled as pace 1.18 because its original report did not specify pace. Human listening is still needed to confirm the preferred pronunciation; text/WAV checks alone do not prove naturalness.

Latest update: see `latency-memory-awareness-research.md` for restrained affection, language-switch recovery, transcript bubbles, context, explicit memory commands and QC/latency controls.

## Written language: Manglish

### Conversational delivery update, 2026-10-20

`config/amma.json` and its example contain no Malayalam script. Edit the greeting in Manglish. Before a one-shot greeting, Groq renders its meaning into speech-language text internally without inserting a synthetic user turn into memory; the bubble still displays Manglish. Native scripts remain inside the speech pipeline and existing historical transcripts for accurate pronunciation, not in the editable Amma profile or visible Malayalam bubbles.

`address_by_language` selects `mone` for Malayalam, `beta` for Hindi and `son` for English on each turn. `speech_delivery.style` controls conversational wording and emotional appropriateness, not an acoustic emotion parameter. `speech_delivery.pace` is set to `1.18`; change it to `1.10` for a gentler increase or `1.0` for the old speed. The same saved candidate voices remain selected. Sarvam's documented `pace` control preserves pitch, and `enable_vad` enables supported silence trimming. Do not set `max_audio_duration` alongside pace.

The clone endpoint documents no emotion/style field. A warmer prompt can improve wording and punctuation; teaching-style prosody may still need a relaxed conversational reference recording. No guarantee of fully human emotion or naturalness is implied. See https://docs.sarvam.ai/api-reference/voice-cloning/clone and https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/prepare-reference-audio.

Run `python tools/voice/verify_delivery.py` for an opt-in paid-provider check using synthetic text. Outputs and a readable report go to `assets/mother/voice/experiments/conversational-delivery-2026-10-20/`. It compares Malayalam at pace 1.0 and 1.18 and generates Hindi and English replies at 1.18. It does not open a microphone or prove subjective voice quality.

All conversation bubbles display Malayalam in Latin letters (Manglish), including face greetings and typed/voice replies. Example: `enthaa mone, sukhamaano?` The display conversion is in `src/manglish.py`, called by `src/app.py` before drawing each bubble. English words stay unchanged. Original Malayalam is retained internally for natural speech synthesis, voice selection and conversation memory. Manglish spelling is phonetic and may differ from personal spelling preferences.

Implemented 2026-10-20. User chose **Amma** and confirmed **karthik** as their enrolled face label. The existing preferred Sarvam voices remain: candidate 8 for Malayalam and candidate 6 for Malayalam–English switching. Groq still decides normal replies.

## Editable profile

Exact private file:

`D:\projects codes\PROJECT SETTA\config\amma.json`

Safe template: `config/amma.example.json`. The real profile is ignored by Git because it can contain family facts. No API keys belong here; keys remain in the root `.env`.

Fields:

- `name`: Amma; used in the prompt and window title.
- `role`: caring, familiar motherly family companion.
- `address_user`: `mone`; used naturally, not mechanically in every sentence.
- `speaking_style`: tone, everyday language, gentle advice/humour, no formal assistant introductions or repetitive service offers.
- `confirmed_facts`: owner-supplied family/user facts. Only relationship and chosen profile name were filled in initially. Add actual facts, not examples or guesses.
- `custom_instructions`: a plain-language system-prompt extension for what Amma should keep in mind. Do not put API keys or other credentials here.
- `greetings`: recognized-owner label, greeting words/language, whether automatic greetings/speech are enabled, confirmation count, absence interval and cooldown.

Edit this JSON and restart the companion to reload it. Keep valid JSON quoting/commas. Conversation turns continue to use automatic Malayalam/English/Hindi detection; the proactive greeting is specifically Malayalam.

The profile prompt asks for a caring motherly style rather than a formal assistant. It avoids repeated AI disclaimers while retaining honest identity answers if directly asked, and it must not invent shared memories or facts. This changes conversational behavior; it does not reconstruct the mother's personal memories or consciousness.

## Memory locations and use

- Character instructions and owner-confirmed facts: `config/amma.json`.
- Existing durable conversation archive and source-labelled facts: `data/memory/companion.sqlite` via the existing `LiveConversation` adapter.
- Normal replies receive a bounded recent/relevant memory bundle in addition to the profile. Retrieved memory remains quoted context, not instructions overriding the profile.
- Spoken automatic greetings are stored as assistant messages. No imaginary user message is inserted to trigger them.
- Existing raw audio references, experiments and checksums remain under `assets/mother/voice/`.

The active model receives the profile facts and selected conversation context. Since Groq is selected, this text is sent to Groq; Sarvam handles the spoken output. The face image/embedding is not uploaded for this greeting mechanism. Face matching is the existing local enrollment implementation; no guarantee of perfect recognition is made.

## Recognition greeting

Configured text:

> enthaa mone, sukhamaano? inn divasam engnganeyuntaayirunnu?

The enabled profile is restricted to face label `karthik`; unknown faces and other family labels do not receive this son greeting. It requires two consecutive matching callbacks. A successful greeting is followed by a 600-second cooldown, and continued presence never triggers another. A return needs at least 30 seconds without the owner's match, then two confirmations. The camera's callback timing/recognition quality still affects when this happens.

Busy voice sessions, muted speech and in-progress reply/talk states defer greetings. A dedicated one-shot speech worker uses the saved candidate voice and does **not** open a microphone or start voice chat. It shares the voice worker slot so greeting and conversation playback do not overlap. Normal mute and Stop Voice Chat controls can stop speech.

Because the user explicitly requested spoken recognition greetings, `greetings.enabled` and `greetings.speak` are true in the private profile. Set `enabled` false to disable automatic greetings. Muting spoken replies suppresses them for the current process. Voice Chat still requires a separate explicit activation to open the microphone.

## Verification

59 regression tests passed, including profile prompt/facts, owner-only consecutive matching, presence/absence/cooldown behavior, and no microphone opening when queuing a greeting. A live provider check generated one greeting and one reply to a synthetic Malayalam question using the actual profile. Private records and WAVs:

`assets/mother/voice/experiments/amma-profile-2026-10-20/`

Those provider files establish generation success, not the user's live face being correctly recognized or physical speaker receipt. Live identity-triggered timing and the user's subjective assessment of warmth need real-use observation. The existing user approval of cloned-voice resemblance is preserved.
