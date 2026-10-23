# Expressive Amma and a proactive study companion

Research only, 21 October 2026, Asia/Kolkata. No app code, voice IDs, settings,
monitoring behavior or provider accounts were changed. No new voice samples
were uploaded, generated or used for training in this investigation.

## Findings about the teaching tone

The current implementation uses saved Sarvam clones through `/voices/clone`,
with a 1.18 pace setting. The reply model controls the words, while synthesis
controls the voice's delivery. Sarvam's reference guidance explicitly says
pace, energy and emotion are copied from the reference. A teaching recording
can therefore carry a teaching cadence into new conversational text. This is a
plausible explanation for the owner's listening observation, not an acoustic
diagnosis of every generated clip. Noise removal cannot reconstruct casual
intonation missing from the original performance.
[Sarvam reference guidance](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/how-to/prepare-reference-audio).

Sarvam's saved-clone generation API documents pace, normalization and duration
controls, but no per-utterance emotion or sarcasm parameter. Pace is explicitly
pitch-preserving. Its create endpoint supports the style label `conversational`,
alongside other categories; the documentation does not establish this as a
guarantee of independent emotional control. It merits an isolated comparison,
not an unsupported new field on production requests.
[Create voice](https://docs.sarvam.ai/api-reference/voice-cloning/create-voice),
[Generate speech](https://docs.sarvam.ai/api-reference/voice-cloning/clone).

## Recommended voice experiments

1. Preserve the approved clones as the baseline. Find a clean casual interlude
   in the existing material, or use a new ordinary conversation recording if
   available. Select a steady 10–15-second sample in the desired everyday style.
2. Compare the current reference against that conversational reference, with
   the same test sentences, language, pace and loudness. Also compare the
   documented conversational creation label. Check the account's clone capacity
   before creating variants; do not delete approved voices to make room.
3. Separate word choice from performance. A proposed response planner could
   produce plain spoken text plus an internal delivery label: neutral, playful,
   concerned, encouraging or firm. Each provider adapter must map only to
   controls it actually supports. Do not send bracketed emotion tags to Sarvam
   and assume they work; they may be spoken aloud or ignored.
4. If appropriate genuine references exist, compare separate style references
   from the same person. Avoid random style switching or word-by-word synthesis:
   identity, accent and continuity may drift. A single improved baseline should
   come first.
5. Consider a second TTS engine only if these comparisons miss the target.
   Changing the reply prompt cannot by itself guarantee different vocal prosody.

Sentence length, contrast, punctuation and a well-timed pause help express a
joke. Uniformly changing speed, pitch or volume is not equivalent to sarcasm
and can damage likeness. A scolding voice need not become louder; clear,
slightly firmer phrasing can be more familiar than theatrical anger. The
owner's preference for few fillers and restrained affection remains a design
constraint. Voice-specific prompting benefits from concrete audible behaviors
and evaluation, rather than generic personality adjectives.
[LiveKit voice prompting](https://docs.livekit.io/agents/start/prompting/).

## Alternative engines checked

| Candidate | Relevant capability | Limitation for this project |
|---|---|---|
| Sarvam current clone route | Existing likeness, Malayalam/Hindi/English; conversational creation label | No documented per-line emotion control on the clone endpoint inspected |
| ElevenLabs expressive models | Audio-tag controls; current v3/v4 documentation includes Malayalam, Hindi and English | Requires a new provider clone and listening comparison; Sarvam voice IDs are not portable |
| Qwen3-TTS | Open-weight cloning and instruction-driven style capabilities | Its documented base language list lacks Malayalam and Hindi; CustomVoice instruction demos are not proof of controllable arbitrary mother's clones |
| Chatterbox Multilingual | Reference cloning and exaggeration controls; Hindi/English documented | Malayalam is absent from the inspected list; Malay is a different language |
| Fish Speech | Cloning and natural-language control; research candidate | Hardware, exact checkpoint language quality and licensing need evaluation; not established as a laptop-ready Malayalam replacement |

Sources: [ElevenLabs models](https://elevenlabs.io/docs/overview/models),
[audio tags](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-do-audio-tags-work-with-eleven-v3-and-v4),
[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS),
[Chatterbox](https://github.com/resemble-ai/chatterbox),
[Fish Speech](https://github.com/fishaudio/fish-speech).

No engine above was installed, benchmarked or heard in this research turn.
Provider latency claims are not end-to-end laptop measurements. Fine-tuning is
a later option requiring suitable varied data and a supported model; a long
set of teaching recordings does not automatically provide casual performances.

## Proactive study mode

Treat this as an explicitly started study session with an agreed task, duration,
allowed apps, breaks, strictness, quiet periods and a stop/snooze command. Five
hours is an example request, not a session started by this document. Clarify
whether the goal means five elapsed hours or five active study hours. Store
wall-clock timestamps with the user's timezone, and use monotonic timers while
the process is running. Persist interruptions, breaks and progress so restarting
does not silently reset the commitment.

Suggested flow:

`study agreement → local observations → sustained-distraction check → nudge policy → brief words → delivery → feedback`

Amma already has local foreground-app history, local memory, reminder machinery
and interaction timing gates. These are building blocks, not an implemented
study coach. The new policy should own proactive prompts and reuse the same
audio queue so reminders cannot collide with a conversation.

### What the observations actually establish

| Signal | Useful evidence | Does not establish |
|---|---|---|
| WhatsApp foreground on Windows | The app/window is active and for how long | Whether the person is chatting, or whether it is unrelated to studying |
| WhatsApp Web | A browser watcher or selected window metadata may identify the tab | A generic browser process name alone cannot identify WhatsApp |
| Phone detected by camera | A phone-shaped object appears in frame | That the owner is using it, what is on it, or whether it is a study tool |
| Phone near tracked hands across frames | Stronger candidate for phone interaction | Motive, emotion, or certainty that the interaction is distracting |
| Missing camera evidence | No usable visual observation | Proof the person has stopped using the phone |

Windows exposes foreground-window metadata. ActivityWatch is a useful local
architecture reference for active apps, AFK and browser watchers; it need not be
installed because this app already collects some metadata. Neither mechanism
requires reading WhatsApp messages.
[Windows API](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow),
[ActivityWatch](https://activitywatch.net/).

For camera sensing, benchmark a small local object detector and combine phone
boxes with the existing hand/face observations. MediaPipe supports object
detection from video; COCO-based models commonly include a cell-phone class.
The relation to hands and persistence over time must be built and evaluated
separately. Downward gaze alone is too ambiguous. A starting experiment might
sample around 1 frame/second and require 10–20 seconds of supporting evidence;
these are proposed settings, not validated thresholds. No new cloud camera
uploads are needed for this route.
[MediaPipe object detection](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector),
[COCO classes](https://docs.ultralytics.com/datasets/detect/coco).

If a phone is outside the camera view, desktop observation cannot see its use.
An optional Android companion with explicitly granted usage access could supply
app-use events, but is a separate project and integration, not an available
capability here. [Android UsageStatsManager](https://developer.android.com/reference/android/app/usage/UsageStatsManager).

### Proposed interruption policy

- Outside an active study agreement: no distraction scolding.
- On an ambiguous first event: ask whether the app/phone is part of the task.
- During an allowed break, call, current speech or quiet mode: suppress nudges.
- After a sustained unapproved distraction: one short prompt; start a cooldown.
- On repeated confirmed distraction: a firmer prompt if strict mode was chosen.
- On correction, snooze or stop: accept immediately and reset the escalation.
- On return to work: clear the event without repetitive praise.

A first desktop grace period of 30–60 seconds and a spoken-nudge cooldown of
several minutes are reasonable experiment settings, not research-derived
universal constants. Limit escalation and total spoken prompts. A reminder
every few seconds could disrupt the work it is meant to support; notification
research documents this awareness/disruption tradeoff.
[Microsoft notification field study](https://www.microsoft.com/en-us/research/publication/notifications-and-awareness-a-field-study-of-alert-usage-and-preferences/).

Example Manglish lines to review, not exact imitations of her habitual sayings:

- Uncertain: “WhatsApp padanathinu vendiyaano?”
- Playful, after confirmation: “Innathe syllabus WhatsApp-il aano?”
- Firm: “Anchu manikkoor padikkaam ennu paranjille? Phone pinne nokkaam. Ippo padanathilekku thirichu vaa.”

Firmness can target the agreed behavior without insults, guilt or invented
disappointment. Store the owner's corrections, preferred strictness and the
nudges that helped, rather than assigning personality labels such as lazy.

## Cost and decision making

Use local timers, app classifications, confidence windows, cooldowns and
templates for routine decisions. Call the reply model only after a meaningful
event passes those gates. Laya is optional for genuinely ambiguous text
classification; it cannot detect phones or supply missing evidence and is not
required for the first study-mode policy. Repeating an LLM call for every frame
or app poll would recreate the quota problem. Short approved recurring nudges
could be cached locally if the voice service's terms permit.

## Research acceptance plan

Voice: begin with four short Malayalam sentences across three delivery intents
(12 clips per candidate), then expand to Hindi, English and code mixing. Include
held-out lines beyond the prompt examples. Compare against the approved voice
blindly, scoring likeness, pronunciation, conversational delivery, intended tone,
latency and cost separately. Reject a more expressive candidate if the owner
hears a different person. Measure before considering training.

Study sensing: label ordinary study, a WhatsApp task question, allowed breaks,
brief phone checks, calculator use, long unrelated phone use and an obscured
camera. Measure false nudges/hour, missed sustained distractions, detection delay,
CPU load, interrupted conversations and owner-rated annoyance/helpfulness.
Start in shadow mode with local event logs and no spoken interruptions. No
numeric success target should be claimed until an initial baseline exists.

Recommended build order when implementation is requested: conversational voice
A/B study; desktop-only study sessions; shadow sensing and correction UI; bounded
spoken nudges; camera phone-interaction sensing last. No monitoring or reminder
automation was activated by this research.

Research retrieval note: Agent Reach's GitHub route failed to connect, so primary
documentation/repositories were read with the web tool. Its update check also
failed DNS; no tooling changes were made.
