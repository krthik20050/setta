# Local reply fallback

Groq remains primary; Sarvam STT and cloned speech are unchanged. Recent chat messages are no longer repeated inside retrieved-context JSON. Retrieved cross-session/relevant excerpts are limited to three per category and serialized compactly. The full conversation archive is retained.

ReplyFallback switches to local OmniRoute on network/timeouts, HTTP 408/429 and selected 5xx failures. A quota/service error starts a bounded cooldown respecting numeric Retry-After; primary requests resume after it expires. Authentication and invalid-request errors are not silently rerouted. Tool call messages and results are carried forward, avoiding intentional replay of completed actions. The gateway receives its own key; Groq credentials are never forwarded. Vision requests still use Groq directly.

Install location: .tools/omniroute (ignored by Git). Published npm release 3.8.52 is used because 3.8.53 was not published at setup time. A local Node 22.22.2 runtime avoids changing the system runtime.

Installed and launched successfully on this laptop. Health and login routes returned HTTP 200; the listener is 127.0.0.1:20128. Private gateway state is data/omniroute, with startup logs in runtime/omniroute.*.log. The launcher isolates the gateway from the app's .env and the user's default gateway configuration. No upstream account has been connected by this setup. 102 project tests passed, including mocked fallback and memory deduplication; no real upstream fallback completion or new transcription comparison has been claimed.

Start with `powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-omniroute.ps1`. Read its help for server options. Connect an eligible provider account in its local dashboard, create a gateway API key, and choose a model or combo tested for Malayalam, English/Hindi switching and tool calls. Do not point the fallback back to the same exhausted Groq model/account. No subscription, new account or credit grant is created by installation.

Set OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1, OMNIROUTE_API_KEY to the gateway's key and OMNIROUTE_MODEL to the selected model/combo in the project .env. Blank key/model disables fallback. Restart Amma after configuration. Unrestricted automatic selection and prompt compression are not enabled by this integration. Mock tests verify failure switching and credential isolation; real fallback requires an actual connected upstream.
