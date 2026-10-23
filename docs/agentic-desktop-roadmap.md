# SETTA Agentic Desktop Roadmap

**Status:** Phases 0–4 first workflow implemented for Brave/YouTube; broader
skill coverage and model promotion remain pending.

**Owner:** PROJECT SETTA / Amma  
**Platform:** Windows desktop  
**Last updated:** 2026-10-22

## Goal

Turn SETTA from a command router into a personal desktop agent that can
understand a user's goal, choose an approved skill, execute multiple bounded
steps, verify each postcondition, recover from ordinary failures, and report
the truth briefly.

Example target:

> “Open Brave and play some relaxing music on YouTube.”

Expected behavior:

1. Resolve the goal as `play_media`.
2. Select the `play-youtube-media` skill.
3. Launch Brave.
4. Open YouTube.
5. Search for relaxing music.
6. Select a result.
7. Verify playback.
8. Say “Playing relaxing music on YouTube.”

SETTA must not claim success from a process launch or a generated model
response alone.

## Design principles

- **Least privilege:** skills receive only the tools and permissions they need.
- **Deterministic safety:** rules, permissions, cancellation, step limits and
  dangerous-action checks stay outside the model.
- **Observe before acting:** use fresh app/browser/UI evidence for each action.
- **Verify after acting:** every meaningful step has a postcondition.
- **Honest outcomes:** distinguish completed, blocked, cancelled and unverified.
- **Local-first privacy:** private conversation, profile and desktop evidence
  remain local unless a configured provider is explicitly needed.
- **One execution path:** typed and voice turns use the same planner and
  executor.
- **Small reversible phases:** each phase leaves a tested, usable system.

## Target architecture

```text
speech/text
  -> transcription and language detection
  -> deterministic safety and obvious local rules
  -> fast intent/entity decision model
  -> skill selection and bounded plan
  -> permission/risk gate
  -> step executor
  -> fresh observation
  -> postcondition verification
  -> retry, recover, clarify or stop
  -> concise result and journal event
```

## Phase 0 — Baseline and evidence ledger

**Status:** documented; existing SETTA routing and desktop tools inspected.

Deliverables:

- Keep this roadmap current.
- Record current routes, permissions, tools and limitations.
- Create a benchmark corpus of natural requests, including:
  - “Open Brave.”
  - “Open Brave and play relaxing music on YouTube.”
  - “Hi, good morning, then open Docker.”
  - “Do not open Figma.”
  - “Stop what you are doing.”
- Record route, latency, action, result and confidence without storing secrets.
- Establish a test command and a runtime smoke check.

Exit gate:

- Existing regression suite passes.
- Every proposed action path has a named permission and cancellation boundary.

## Phase 1 — Skill registry and contracts

**Status:** skill registry, bounded executor, deterministic planner and visible
browser adapter implemented for the first workflow.

Create a local registry of bounded skills. A skill is a typed contract, not
just a prompt.

Each skill defines:

- `name` and user-facing description.
- Intent names and required entities.
- Allowed tools.
- Required Profile & Memory capabilities.
- Maximum steps and time budget.
- Confirmation policy.
- Preconditions.
- Postconditions.
- Retry and recovery policy.
- Whether the action is reversible.

Initial skills:

1. `open-app`
2. `search-web`
3. `control-media`
4. `play-youtube-media`
5. `open-document`
6. `summarize-current-page`
7. `set-reminder`
8. `stop-current-task`

The first multi-step skill is `play-youtube-media`. It should initially use
browser navigation and accessibility/DOM evidence; screenshot-driven clicking
is a fallback, not the default.

Exit gate:

- Invalid skill definitions fail closed.
- A skill cannot request an unregistered tool or permission.
- Skill selection is covered by deterministic tests.

Implemented foundation:

- `src/skill_registry.py` defines validated skill contracts.
- `src/task_execution.py` executes only registered skill tools.
- Plans enforce skill step limits and tool allowlists.
- Permission checks, cancellation and postcondition verification fail closed.
- `play-youtube-media` is registered as a bounded skill contract.

The first workflow is now wired through:

- `src/task_planner.py` for natural “play music on YouTube” intent.
- `src/browser_media.py` for a dedicated visible Brave profile.
- `agent_tools.py` for browser/desktop permission checks and playback results.
- `live_conversation.py` for plan execution and concise success/failure text.

The live check launched Brave, searched YouTube for “relaxing music”, selected a
result and verified `video.paused == false` with `currentTime > 0`. Generic
music requests now prefer Spotify when it is installed; explicit YouTube
requests continue through the verified Brave workflow. Spotify search opening
is currently reported as unverified because the desktop URI does not expose a
reliable playback acknowledgement without an authenticated API/session.

Media selection currently uses a fast local decision seam:

- Explicit `YouTube`, `music video` or `video` requests select YouTube.
- Explicit `Spotify` requests select Spotify.
- Generic audio requests prefer installed Spotify.
- If Spotify is unavailable but Brave is installed, generic requests fall back
  to YouTube.
- If neither service is available, SETTA does not execute the plan.

This deterministic selector is the live fallback while Laya remains a
shadow-only classifier. It is intentionally availability-aware and testable;
Laya can later supply structured intent, but cannot bypass this selection,
permission or verification layer.

## Phase 2 — Fast decision model

**Status:** shadow infrastructure exists; promotion is not approved.

SETTA currently has a Laya shadow adapter in `src/laya_shadow.py`. It observes
ambiguous turns and logs a suggested route with `applied=False`. Keep that
boundary while collecting measurements.

The decision model should return structured intent only:

```json
{
  "intent": "play_media",
  "entities": {
    "browser": "Brave",
    "service": "YouTube",
    "query": "relaxing music"
  },
  "mode": "multi_step",
  "confidence": 0.94
}
```

It must not execute tools, bypass permissions, or invent a skill.

Promotion gates:

- p95 routing latency target: 300 ms or less on this machine.
- At least 95% accuracy on the local intent corpus.
- Separate English, Hindi, Malayalam and Manglish measurements.
- Zero unauthorized actions in negative/safety cases.
- Timeout and model failure fall back to deterministic routing.

Until those gates pass, Laya remains shadow-only.

## Phase 3 — Planner and task executor

Add a bounded `TaskPlan` and executor:

```text
plan -> authorize -> execute one step -> observe -> verify -> continue/stop
```

Each step records:

- Step ID and skill name.
- Tool and validated arguments.
- Start/end timestamps.
- Permission decision.
- Observation used.
- Result status.
- Verification status.
- Retry count.

Required controls:

- One desktop execution lock.
- Cancellation token.
- Maximum step count.
- Per-step and whole-task deadlines.
- No arbitrary shell or PowerShell execution.
- No hidden background actions after cancellation.

Exit gate:

- A failed verification cannot be reported as success.
- Cancellation stops the current plan promptly.
- Restarting SETTA does not resume an unfinished external action silently.

## Phase 4 — Browser and native desktop adapters

Prefer capability-specific adapters in this order:

1. Service API.
2. Browser DOM/accessibility tree.
3. Windows UI Automation.
4. Screenshot targeting as a bounded fallback.

For browser work, begin with a dedicated Brave/Chromium session so SETTA does
not unexpectedly manipulate the user's personal tabs. Add active-session
control only behind a separate permission.

For native Windows applications, use UI Automation where accessible controls
exist. Keep app launching through the existing catalog and permission gate.

## Phase 5 — Verification, recovery and continuity

Add postcondition verifiers and bounded recovery:

- Reopen a failed browser page once.
- Retry a search once with normalized terms.
- Select a different result when the first result is unavailable.
- Stop and explain the exact blocked step after the retry budget.

Store task outcomes separately from personal facts. Record enough provenance
to inspect why SETTA claimed a task succeeded or failed.

## Phase 6 — Learning and skill improvement

Use completed task records to improve:

- Preferred browser and services.
- Successful query normalization.
- Common aliases and speech variants.
- Failure patterns.
- User corrections.

Learning may suggest changes or create a draft skill, but it must not silently
grant permissions or activate a new skill. New skills require validation and
explicit enablement.

## Reverse-engineering workstream

Use normal source inspection for open-source repositories and REA for shipped
applications, binaries, packaged runtimes or behavior not established by
source.

Targets:

- Hermes: skills, tool registry, memory, scheduling, subagents and approvals.
- Agent S: observe/act/verify loop and Windows UI adapters.
- OpenAI CUA sample: persistent workers and feedback loops.
- Browser Use: browser navigation and DOM-based action patterns.
- Muse: continuity, evidence and user approval.
- ODD: installed-app catalog and launch fallback behavior.

Every finding must distinguish:

1. **Observation** — directly established by source, artifact or runtime.
2. **Inference** — a reasoned conclusion from that evidence.
3. **Unknown** — not established by the investigation.
4. **Adoption decision** — what SETTA will or will not copy.
5. **Evidence ID/source** — enough detail for another agent to reproduce it.

Keep findings in `docs/reverse-engineering/` and link them from this roadmap.
Do not copy private data, credentials, or proprietary code.

## Documentation required for every implementation phase

Each phase must update:

- This roadmap's status and exit gate.
- A focused design or implementation document.
- Tests for the changed behavior.
- The agent handoff when paths, permissions or runtime behavior change.

## Explicit non-goals for the first release

- Unrestricted terminal, PowerShell or shell access.
- Silent sending of messages, purchases or publishing.
- Controlling every visible application through screenshots.
- Automatic permission escalation.
- Model-generated claims treated as proof of completion.
- Autonomous skill installation from arbitrary internet content.
