# Antigravity connection smoke test

Tested the user's saved Antigravity connection through the local OmniRoute provider dashboard Playground, using only synthetic prompts. Model identifier shown: antigravity/gemini-3.8-flash-low. This is the gateway catalog identifier, not independently verified upstream model provenance.

- Basic per-model connection test: UI reported OK.
- Malayalam one-sentence response: native-script Malayalam returned, roughly meaning "Good, may today's work go well." Dashboard reported 3346 ms, 106 input / 13 output tokens.
- Switch to English: "What part of your project are you working on today?" Dashboard reported 3151 ms, 151 input / 11 output tokens.
- Switch to Hindi: native-script Hindi returned, asking whether the project was finished. Dashboard reported 3603 ms, 188 input / 9 output tokens.

These are three successful short text turns, not an audio, tool-calling, full Amma-profile, sustained-load or end-to-end fallback benchmark. Times are dashboard-reported response timings and exclude microphone, transcription and Sarvam cloned speech. No family memory, screen content, microphone recording or API key was entered into these prompts.

The dashboard flags this provider with usage caveats and excludes it from automatic routing by default. That setting was not overridden. No fallback key/model was enabled in Amma as part of this smoke test. Next integration validation should verify tool-call compatibility and then simulate a Groq failure through the actual companion path before enabling production fallback.
