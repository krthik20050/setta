# Cultural address preference learning

## Observed cause and change

The reply postprocessor translated mone to son for English turns. Language instructions also discouraged carrying an address across languages. This downstream behavior was verified in source; microphone recognition for the reported utterance was not reproduced.

Explicit requests now override language defaults. `Call me mone once` applies only to the current response. `Call me mone in English` saves a language-specific preference; `Call me mone` saves a general preference. Quoted/past requests and scheduling phrases such as `Call me tomorrow` are not promoted. The parser currently supports a narrow set of English request forms; this is not unrestricted semantic preference extraction.

Facts use the existing local database `data/memory/companion.sqlite`, with the original user-message ID as provenance. They can be inspected and removed in Profile & Memory. Recall-disabled mode does not retrieve saved address preferences. Explicit once-only requests still work.

The native WAV synthesis path renders the selected word with Malayalam text/language, retaining the clone selected for the original conversation. Display text remains Manglish. Mixed sentences require separate synthesis requests and concatenation, which may add latency or audible boundaries. The older streaming speech endpoint has not received this segmentation change. No approved clone was retrained or replaced.

## Learning architecture

Hermes distinguishes persistent personal facts/preferences from procedural skills and searchable session history:

- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- https://hermes-agent.nousresearch.com/docs/guides/work-with-skills

For Amma, grow this incrementally: explicit correction -> sourced preference -> relevant retrieval -> application -> user correction/deletion. Future semantic extraction should distinguish quotations, temporary wishes and uncertainty before proposing a durable fact. Emotional adaptation should use the user's stated preferences and context, without claiming to know unspoken feelings. This is personalization, not model-weight training or evidence of human emotional experience.

## Verification

180 local regression tests passed, including one-time versus durable storage, restart retrieval, cross-language preservation, quoted requests, scheduling ambiguity, and mocked synthesis language/clone selection. Live listening and microphone recognition remain separate verification steps.
