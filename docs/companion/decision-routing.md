# Local decision routing

Implemented 21 October 2026. Rules run before reply generation in the shared
`LiveConversation` adapter, so native voice and text use the same decisions.

Laya is now installed and operational in shadow mode. Run
`python tools/check_laya.py` from the project root to verify the local
checkpoint and worker. Shadow decisions are still observational: they are
recorded but cannot execute tools or replace the deterministic planner.

## Active behavior

Exact English questions about the current time, today's date, or a saved user
name get a local answer. Missing names, compound questions and other languages
continue to the existing reply model. Camera and desktop questions keep their
existing evidence checks. Replies still enter local conversation memory and the
conversation journal; Sarvam still handles speech. Only the reply-generation
request is skipped for these simple answers.

## Optional Laya evaluation

Laya 0.4.12 is installed in
`D:\projects codes\PROJECT SETTA\.tools\laya-env`. It inherits installed Python
dependencies through system-site-packages; it is not a fully isolated lockfile.
The adapter starts a private CPU subprocess when `LAYA_SHADOW=1` in the root
`.env`. It is enabled in the current project configuration. Restart Amma
after changing it.

The worker evaluates ambiguous requests in the background and logs a suggested
route with `applied=false`. It never authorizes tools, changes replies, commits
memory, or controls microphone/turn boundaries. API credentials are removed
from its environment. Runtime model downloads are disabled. No text is sent to
a remote inference provider by this worker.

Only one shadow worker across conversation instances may hold the model lease.
The queue holds one waiting request; excess requests are skipped. Inference has
a 120-second watchdog, and errors disable that instance until restart. Only one
checkpoint is kept loaded, with two CPU inference threads. The second live
conversation instance does not acquire a second heavyweight model.

English uses the English checkpoint; Malayalam/Hindi and code-mixed requests
use the multilingual checkpoint based on the transcription language. Accuracy
on Manglish and local camera/desktop intent still needs a labelled evaluation.

The worker currently classifies `reply_model`, `memory_search`,
`camera_observation`, `desktop_context`, `desktop_action`, `play_media` and
`multi_step_task`. It remains advisory until the latency, confidence and
held-out accuracy gates are measured on this machine.

## Locations

| Item | Absolute path |
|---|---|
| Rules | `D:\projects codes\PROJECT SETTA\src\decision_router.py` |
| Shadow adapter | `D:\projects codes\PROJECT SETTA\src\laya_shadow.py` |
| Private worker | `D:\projects codes\PROJECT SETTA\tools\laya_worker.py` |
| Model cache | `D:\projects codes\PROJECT SETTA\.tools\laya-model-cache` |
| API settings and opt-in flag | `D:\projects codes\PROJECT SETTA\.env` |
| Decision events | `D:\projects codes\PROJECT SETTA\data\conversation-archive\events.sqlite` |
| Conversation memory | `D:\projects codes\PROJECT SETTA\data\memory\companion.sqlite` |

Events include `decision_route`, `decision_shadow`, `decision_shadow_error` and
`decision_shadow_skipped`. Shadow records contain suggested route, baseline
route and elapsed inference time, not a separate copy of the transcript. The
existing conversation journal already stores transcripts locally.

## Verification and limits

127 regression tests passed, including provider-bypass and durable-memory
checks for local answers. This is source-level verification, not a spoken
microphone test. Downloading the public weights was attempted; inference and
laptop latency are not yet verified. Keep shadow mode disabled until a local
benchmark completes, then evaluate held-out English, Hindi and Malayalam/code
mixed examples under the real camera workload before promoting any routing.

This change does not implement echo cancellation, streaming transcription or
the planned replacement turn controller. Those remain the priority for
premature replies and speech interruptions.
