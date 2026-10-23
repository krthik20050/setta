# Groq conversation failure diagnosis

Reproduced with synthetic English turns through LiveConversation and an isolated temporary memory database. No microphone, private conversation or desktop content was used.

Groq returned HTTP 429, code rate_limit_exceeded, type tokens, for openai/gpt-oss-20b. Its response stated a tokens-per-minute limit of 8000, used 6969 and requested 2079, with retry-after 8 seconds. This demonstrates a per-minute quota failure, not a rejected key or evidence of an exhausted credit balance. It does not establish every historical failure had the same cause.

The old catch-all message obscured the cause. Provider failures now produce specific safe messages and write only status, category, model, numeric quota headers and retry timing to runtime/reply-provider-error.json. Prompts, raw provider bodies, organization identifiers and credentials are excluded. Both native voice and browser hands-free paths receive the safe error.

OmniRoute is a gateway, not a model or credit grant. It requires eligible upstream connections. Recommended next integration: keep Sarvam recognition and cloned speech; retain Groq as primary; configure a separately tested upstream fallback through OmniRoute. Validate Malayalam, English/Hindi switching, latency and tool calling before selecting a default. Avoid arbitrary automatic model selection and prompt compression until personality and pronunciation behavior have been checked. No OmniRoute installation or provider change was made during this diagnosis.

Sources: https://console.groq.com/docs/rate-limits and https://github.com/diegosouzapw/OmniRoute
