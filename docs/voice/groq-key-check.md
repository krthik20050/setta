# Groq credential check — 2026-10-20

Final verification update: 48 local tests passed, including a control to enable/mute spoken replies. Both entry points use the shared conversation adapter configured as Groq. Four real synthetic-input provider checks completed and all generated WAVs passed hash/full-decode checks. Updated app relaunched for user testing; choose **Enable spoken replies** and then **Voice Chat (Alt+M)** in its right-click menu. Logs are under `runtime/`. Physical mic/speaker conversation is not yet verified.

Subsequent integration update: user explicitly requested switching the companion to Groq. Implemented `REPLY_PROVIDER=groq` in the root `.env`, with `GROQ_MODEL=openai/gpt-oss-20b`. `src/sarvam_conversation.py` now uses a separate Groq client for replies; Sarvam STT and selected cloned voices are unchanged. Four live synthetic-input recognition -> Groq reply -> cloned-speech checks passed (Malayalam, English, Hindi, mixed), and 47 regression tests passed. Results are in `assets/mother/voice/experiments/groq-conversation-smoke-2026-10-20/`. The older key-check-only statement below describes the prior checkpoint. No silent fallback to the rejected OpenAI key occurs while Groq is selected.

The user supplied a Groq key, initially on a malformed standalone line in the root `.env`. It was moved into a valid `GROQ_API_KEY` assignment without displaying or logging it. This is Groq, not xAI/Grok and not an OpenAI API key. The existing other provider assignments were preserved.

Authenticated GET `https://api.groq.com/openai/v1/models` returned HTTP 200. A minimal chat completion using the available `openai/gpt-oss-20b` model returned HTTP 200 and `Connection working.`. No microphone audio, family reference audio, or personal conversation was sent. The result is saved locally at `assets/mother/voice/experiments/groq-auth-2026-10-20/verification.json`.

Only credential syntax and provider access were fixed/tested here. The desktop reply-generation implementation still selects OpenAI when `OPENAI_API_KEY` is set; it has not been changed to use Groq. A successful Groq key test is not proof of that application integration or multilingual reply quality. The `GROQ_MODEL` environment entry was corrected to the model verified available in this account.

Official provider documentation: https://console.groq.com/docs/overview and https://console.groq.com/docs/models .
