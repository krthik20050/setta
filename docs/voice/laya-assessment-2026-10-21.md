# Laya's role in Amma

Decision: optional text-decision component; not a prerequisite for the voice rebuild. Follow-up implementation installed Laya 0.4.12 in a separate local environment and added an opt-in shadow adapter. Shadow remains disabled; inference is not yet verified. Narrow local rules now bypass reply generation for English time, date and saved-name questions. See [implementation and verification](../companion/decision-routing.md).

Inspected the official README, laya/router.py, docs/benchmarks.md and guardrail limitations through GitHub. Laya returns typed decisions over text rather than processing microphone waveforms. Its stated 33-ms reference is a T4 measurement, not this laptop's latency. The repository reports major gains from domain-specific fine-tuning and documents confidence/calibration caveats. Its multilingual routing does not establish Malayalam/Manglish turn-completion accuracy. Sources: [repository](https://github.com/NandhaKishorM/laya), [router](https://github.com/NandhaKishorM/laya/blob/main/laya/router.py), [benchmark guidance](https://github.com/NandhaKishorM/laya/blob/main/docs/benchmarks.md).

## Proposed uses and boundaries

| Decision | Assessment for Amma |
|---|---|
| Retrieve memory, use a tool, or answer directly? | Good candidate for a short text intent-routing evaluation. |
| Does an evolving transcript look unfinished? | Possible supporting signal after training/evaluation; must not independently override acoustic evidence. |
| Is this an intentional interruption or a backchannel? | Text can contribute after a meaningful partial transcript, but timing, speaker echo and audio context remain essential. |
| Is microphone audio speech or noise? | Requires an audio detector, not Laya's text input. |
| Remove Amma's speaker echo? | Requires AEC and synchronized render-reference audio. |
| Generate natural replies or clone the mother's voice? | Keep the reply model and Sarvam clone for those jobs. |

## If evaluated

Run Laya in shadow mode first: log its suggestions without allowing it to stop audio, answer prematurely, save personal facts or execute tools. Give it a short state with the original native-script transcript, known language and candidate decisions. Keep Manglish as display output; Latin-script transliteration can make automatic language routing ambiguous. Verify the multilingual checkpoint explicitly for Malayalam/code mixing rather than trusting a language-count headline.

For completion labels, include incomplete and complete phrases with the same prefix: "I am going to wash" versus "I am going to wash the laundry." Include hesitations, corrections, short complete answers, code mixing and silence-induced STT hallucinations. A transcript alone can leave completion genuinely ambiguous; provide WAIT/UNCERTAIN and fall back to a patient policy.

Compare against the same streaming controller without Laya. Measure premature commits, missed interruptions, phantom replies and p50/p95 decision delay under the real camera/animation workload. Include loading time and memory use. Use held-out labelled examples; calibrate uncertainty on those decisions and abstain when unsure. Add the component only if it improves measured conversation behavior without unacceptable delay or complexity.

Laya can reduce how often a large reply model handles simple classification. It does not reduce provider audio costs or create free model credits. It must not become another independent owner of turn boundaries alongside STT VAD and a separate endpoint detector.
