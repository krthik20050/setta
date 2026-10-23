# Native realtime input and conversational style

Implemented 21 October 2026 in the desktop application. No browser preview is
involved. The saved Sarvam mother voice, speed and pronunciation path remain
unchanged. This changes transcription, turn assembly, and reply prompting.

## Diagnosis

The previous native path used SpeechRecognition's silence endpoint (2.2s),
then uploaded the entire recording to REST STT. Every accepted recording called
`interrupt()` before its transcript was known. A short noise recording could
therefore cancel valid playback. A 27-second recording cap discarded longer
utterances. User text was available only after recording and REST recognition.

A snapshot of the most recent 300 journal events contained 38 native captures,
11 interrupted replies, 5 speaker-overlap rejections and 4 capture-limit events.
One recent capture had peak RMS 35.8. These are diagnostic indicators, not proof
that all captures or interruptions were noise. No private recording was uploaded
for this investigation.

## Implemented behavior

The native input now streams mono PCM16 at 16kHz to Sarvam's
`/speech-to-text-realtime/ws`, `saaras:v3-realtime`, automatic input language,
fast partials and codemix finals. Partials revise the bubble while the person is
speaking and never invoke tools, the reply model, or durable conversational memory.
Final segments are joined until the continuation hold expires. The provider
silence setting is 2200ms plus a local 650ms hold, or 1500ms after a few English
unfinished endings. New speech cancels that pending commit. This heuristic is
patient endpointing, not a trained semantic completion detector.

Only a nonempty committed transcript can supersede a reply. Generation IDs
still prevent stale playback. An answer being prepared waits before starting
its next spoken chunk if the user is continuing. The default REST fallback no
longer cancels a reply because an untranscribed recording ended.

The new path has no 27-second utterance cutoff. The local WAV audit buffer rolls
at five minutes; longer text remains assembled, so that WAV can contain only the
last five minutes. This is not an unlimited provider session guarantee. If the
socket fails, Voice Chat stops with a recoverable message; restart it. Automatic
reconnect and robust session rollover are not implemented yet.

During playback, microphone frames are replaced by silence before transport,
followed by a 500ms speaker-tail gate. **This is half-duplex echo protection, not
AEC.** Reliable voice interruption while Amma speaks remains future work. Use
the existing manual interrupt control. The connection runs only during Voice
Chat; continuous streaming can bill silence as audio duration under the
provider's policy. There is no second REST transcription request in this path.

The bubble follows recent words during partials, preserves the user transcript
while thinking, and shows reply captions before each spoken chunk. Its existing
display conversion keeps Malayalam readable as Manglish.

## Conversational prompt tuning

`conversation_style` in the local profile now asks for brief spoken replies,
contextual references, acceptance of self-corrections, varied openings, optional
light humor, and serious responses when the topic changes. Concrete tone examples
discourage canned praise and unjustified reassurance. This is prompt tuning,
not training new model weights or changing the voice clone.

A two-case synthetic provider check initially produced generic praise and
reassurance. After concrete examples, the playful case produced a light joke
and the exam-worry case asked a relevant question. These were illustrative
examples also used in the prompt, not a held-out quality benchmark. Humor,
Malayalam/code-mixed style and naturalness still need the owner's listening
review and more varied test cases.

## Verification and exact locations

132 regression tests passed. Cases cover partial revision without premature
commit, continuation across final segments, an empty final, 60 seconds without
an artificial 27-second commit, shared native dispatch, and retained REST mode.
The actual Sarvam socket accepted the existing key. A generated Windows speech
fixture produced 31 partial updates, first at 0.988s, and the complete expected
English transcript committed at 7.782s from stream start. This includes fixture
playback and endpointing; it is not total reply latency or a real microphone test.

| Item | Absolute path |
|---|---|
| Realtime input | `D:\projects codes\PROJECT SETTA\src\realtime_input.py` |
| Native voice lifecycle | `D:\projects codes\PROJECT SETTA\src\sarvam_voice.py` |
| Desktop transcript bubble | `D:\projects codes\PROJECT SETTA\src\app.py` |
| Editable personality | `D:\projects codes\PROJECT SETTA\config\amma.json` |
| Shared prompt builder | `D:\projects codes\PROJECT SETTA\src\character_profile.py` |
| Environment | `D:\projects codes\PROJECT SETTA\.env` |
| Final transcripts, events and WAVs | `D:\projects codes\PROJECT SETTA\data\conversation-archive` |
| Conversation memory | `D:\projects codes\PROJECT SETTA\data\memory\companion.sqlite` |
| Health status | `D:\projects codes\PROJECT SETTA\runtime\native-voice-status.json` |
| Provider smoke evidence | `D:\projects codes\PROJECT SETTA\runtime\realtime-input-smoke.json` |
| Style smoke evidence | `D:\projects codes\PROJECT SETTA\runtime\conversation-style-smoke.json` |
| Reproducible synthetic check | `D:\projects codes\PROJECT SETTA\tools\verify_realtime_input.py` |

`SETTA_REALTIME_INPUT=1` enables the new default. Set it to `0` and restart Amma
to restore legacy REST input if required. Dependencies now include websockets
>=15,<17; this laptop currently has 16.0. Laya remains disabled and does not
participate in turn completion.

## Research used

Sarvam documents real interim transcripts, automatic language detection and
manual/VAD endpointing on this newer endpoint. Its legacy socket does not emit
real partials. [Realtime protocol](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming).

LiveKit separates endpointing from interruption handling and supports resuming
speech after false interruptions. This supports avoiding raw audio-triggered
cancellation; the full adaptive model was not installed here.
[Turn tuning](https://docs.livekit.io/agents/logic/turns/tuning/).

Its voice prompting guidance recommends short spoken replies, explicit audible
personality behaviors and real-world evaluation. We adapted those ideas to the
owner's preference for few fillers and restrained affection.
[Prompting guidance](https://docs.livekit.io/agents/start/prompting/).

Agent Reach's Exa backend was not configured, so research used the web tool and
official documentation. Its update check also failed DNS; no tooling update was
attempted.
