# Groq quota recovery

Implemented 21 October 2026. Latest saved Groq diagnostic was HTTP 429, classified
as rate_limit. That proves a quota/rate rejection, not an empty credit balance.
The saved response did not include remaining-token headers, so its exact window
cannot be established from that record alone.

Groq currently lists GPT-OSS 20B's free limits as 8K tokens/minute, 30 requests/
minute, 1K requests/day and 200K tokens/day. Organization-specific limits can
differ. They are shared across keys/apps in the same organization. Creating
another key or installing OmniRoute does not provide additional free quota.
[Official rate limits](https://console.groq.com/docs/rate-limits).

## Why short conversations hit the limit

Every request carries the profile, response policy, recent messages, retrieved
memories and tool definitions. Tool use can need two or more model requests
for one spoken answer. Language repair can add another. Live internet search
uses a separate Groq request under the same account. Reply duration alone does
not measure token use. GPT-OSS reasoning tokens also consume output budget.

## Changes now active

- Groq uses a compact profile: 2,239 characters instead of 4,379 in the measured
  current configuration. This is a character comparison, not a measured 49%
  reduction in total request tokens.
- Recent messages sent to Groq are limited to four rather than six. The prompt
  gets two relevant older messages and one cross-session message. Confirmed
  facts have a bounded prompt view, prioritizing name/home. All local memory
  remains stored and searchable; omitted-fact count is explicit.
- Exact plain greetings omit tool schemas. Other requests keep the tool
  capabilities. The current user utterance is not truncated.
- A Groq 429 or transient failure can fall back to a separately authenticated
  Sarvam chat client. Sarvam 105B Conversations was tested live for text and
  function calls. The same validated tool loop and current language instructions
  continue through fallback. The saved mother voice is unchanged.
- Cooldown is shared across companion clients in this process, keyed by primary
  account fingerprint and model. Credentials/fingerprints are not logged. The
  app honors retry-after, or extracts a numeric retry interval from the error
  when available. It does not repeatedly retry while waiting for quota.
- If explicitly configured, OmniRoute is tried first and Sarvam is the next
  independent fallback. OmniRoute remains unconfigured here: its key and model
  are blank. Nothing is claimed to work through that gateway.

The root `.env` now contains `SARVAM_REPLY_FALLBACK=1`. Setting it to `0` and
restarting disables the independent fallback. No new API key was needed.
Sarvam fallback uses Sarvam's own balance/limits; it is not free or unlimited
by virtue of being fallback. If both providers fail, the app reports the failure.

Groq's automatic cache can help with stable prompt prefixes. Static instructions
remain before changing context. Cache hits are not guaranteed and were not
claimed as measured savings. [Official caching guidance](https://console.groq.com/docs/prompt-caching).

## Verification

158 regression tests passed. New tests cover independent credentials, preserving
tool-result messages, payload translation, cooldown shared across clients,
safe telemetry and keeping memory intact while compacting its prompt view.

A synthetic primary 429 was injected while allowing the secondary HTTP calls
to reach the real Sarvam API. Sarvam requested get_weather, received the real
Kochi/Kerala/India weather result, and generated an English answer. The complete
fault-injection check took 2.382 seconds. Host sequence was Groq (simulated 429),
Sarvam, Sarvam. This is a real secondary-provider check, not proof of a naturally
occurring Groq outage or a full microphone conversation.

## Diagnostics and locations

| Item | Absolute location |
|---|---|
| Configuration | `D:\projects codes\PROJECT SETTA\.env` |
| Fallback and shared cooldown | `D:\projects codes\PROJECT SETTA\src\reply_fallback.py` |
| Compact profile | `D:\projects codes\PROJECT SETTA\src\character_profile.py` |
| Compact retrieval view | `D:\projects codes\PROJECT SETTA\src\companion_context.py` |
| Usage and quota telemetry | `D:\projects codes\PROJECT SETTA\runtime\reply-usage.jsonl` |
| Last explicit Groq error | `D:\projects codes\PROJECT SETTA\runtime\reply-provider-error.json` |
| Live injected-429 evidence | `D:\projects codes\PROJECT SETTA\runtime\quota-fallback-smoke.json` |

Usage telemetry stores provider/model, HTTP status, request character count,
message/tool counts, numeric token usage, cached tokens and safe quota headers.
It does not contain prompts, replies, API keys or provider error bodies.

## Remaining limits

News/general web search still uses Groq. A conversation can fall back to Sarvam,
but that does not give the Groq browser tool independent quota. Weather itself
uses Open-Meteo and does not spend Groq search tokens. Independent search would
need a separate search backend, key or suitable feed source.

For sustained use, the predictable options are higher approved Groq limits or
another separately provisioned provider. No billing changes were made. Switching
between same-limit models or keys is not presented as a way around account limits.
Monitor real usage during ordinary sessions before choosing a paid tier.
