# Voice cloning research — 2026-10-20

## Recommendation

Test Sarvam first for one hosted voice across Malayalam, Hindi, and English; compare IndicF5 locally for Malayalam/Hindi and Chatterbox for Hindi/English. These are candidates based on documented capabilities, not a measured quality ranking for this speaker. No model has been run on her recordings yet. Do not promise perfect or indistinguishable output.

## Candidate comparison

| Candidate | Language fit | Cost and limitations |
| --- | --- | --- |
| Sarvam Instant Voice Cloning beta | Malayalam, Hindi, Indian English; cross-language reference support | Docs list Rs 100 new-user credits and Rs 30 per 10,000 generated characters; free plan retains up to five clones. Trial credit is not unlimited free use. Streaming available. Confirm actual account access and billing before running. |
| AI4Bharat IndicF5 | Malayalam and Hindi among 11 Indian languages; English is not listed | Model card labels weights MIT. Local computation still needs hardware, storage, electricity. Reference audio plus exact transcript required. Good first local Indian-language candidate. |
| Resemble Chatterbox Multilingual | Hindi and English; Malayalam absent from official general model list | MIT repository. Local inference candidate; third-party Malayalam adapters require separate evaluation. |
| Qwen3-TTS | Official repository lists Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian | Apache-2.0 repository; useful English comparison, not the primary Hindi/Malayalam solution. Use Base variant for reference voice cloning; CustomVoice is not synonymous with arbitrary speaker cloning. |
| ElevenLabs | Language support varies with synthesis model; verify the exact model selected | Pricing page lists Instant Cloning on Starter at USD 6/month, Professional on Creator at USD 22/month, first month USD 11; taxes extra. Free TTS is not free voice cloning. Professional clone must be created and verified by the voice owner. |
| Coqui XTTS-v2 | Hindi and English, no Malayalam in official model-card language list | Coqui Public Model License, not MIT/Apache. Review use terms. Secondary comparison, not full language coverage. |
| OpenVoice V2 | Six natively supported languages include English, exclude Hindi/Malayalam | MIT. Tone conversion can be combined with another language TTS system, but adds engineering and another source of pronunciation/prosody differences. |
| RVC | Converts existing speech rather than directly generating speech from text | Open-source voice conversion alternative. Upstream recommends at least 10 minutes of low-noise speech. Can test a language TTS followed by conversion; does not automatically reproduce the mother's speaking rhythm. |

## What the voice enables

New spoken replies, reading text or stories, teaching-assistant narration, multilingual lesson narration, and personal voice-agent output. Knowledge and personality grounding require separate content/retrieval work. Authentic original recordings remain the most faithful option for existing phrases. Label generated output as synthetic when shared.

## Architecture and ownership

Speech recognition -> interchangeable text-generation model -> separate cloned-voice TTS service -> audio playback. Changing the text model does not require changing the voice service. Hosted voice IDs are provider-scoped; they are not universal downloadable voice models. Retain original recordings, transcripts, source timestamps, and locally trained checkpoints where licensing permits.

## Quality plan

1. Archive owner-provided originals and create a timestamped single-speaker dataset.
2. Compare multiple clean references before training anything.
3. Generate matching short texts in all three target languages, including names, numbers, and natural code switching.
4. Ask family listeners to judge resemblance independently of pronunciation. Hold out original speech from any training set for comparison.
5. If short-reference cloning is inadequate, investigate speaker fine-tuning only for models with verified training support; use clean transcribed data and a held-out validation set. Training more noisy audio can worsen results.
6. Measure latency before selecting a live-agent backend. Natural offline narration does not prove real-time suitability.

## Sources checked

- https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/overview
- https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/supported-languages
- https://docs.sarvam.ai/api/getting-started/pricing
- https://docs.sarvam.ai/api/getting-started/commercial-licensing
- https://github.com/AI4Bharat/IndicF5
- https://huggingface.co/ai4bharat/IndicF5
- https://github.com/resemble-ai/chatterbox
- https://github.com/QwenLM/Qwen3-TTS
- https://elevenlabs.io/pricing
- https://elevenlabs.io/docs/help-center/product/voices/voice-cloning/can-i-create-a-professional-voice-clone-of-someone-elses-voice
- https://huggingface.co/coqui/XTTS-v2
- https://docs.myshell.ai/technology/openvoice
- https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI

This is a targeted survey of primary project/model documentation, not an exhaustive search of the entire internet. Prices and beta access may change. No provider purchase, upload, training, or voice generation was performed.
