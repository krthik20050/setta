# Profile, memory and local actions

Implemented 21 October 2026, Asia/Kolkata. This is a working single-companion
foundation, not a released multi-user relationship platform or autonomous
study-enforcement system.

## What to try

Open Setta → **Profile & Memory**. Settings also links to this page.

- Edit the existing name, role and custom instructions with Save profile.
- Choose calm, playful, firm or strict tone; edit speech speed and address terms
  separately for Malayalam/Manglish, Hindi and English.
- Enable or disable capabilities with Save capabilities. Changes merge into the
  existing profile; voice IDs, pronunciation rules and unrelated config survive.
- Inspect confirmed facts, add/correct a fact, remove its saved-fact entry, or
  search earlier conversation text. Removing a fact is not deleting its original
  conversation or audio archive.

Strict is a conversational tone, never an implicit grant of desktop access.
The permission checks are in action execution, not only in the prompt. Camera
and active-app permissions also gate observation use; disabling them stops their
current capture/polling through the settings flow. Disabling memory recall stops
retrieved conversation/fact injection and memory-search tools, but does not stop
local chat recording. Manually configured profile facts remain part of the
profile. Selected context still goes to the configured reply provider.

Permissions cover local arithmetic, timers, approved apps/documents, filename
search, internet tools, conversational recall, active-app metadata and camera
observations. These switches do not create arbitrary app typing, shell access,
app closing, message sending or automatic distraction enforcement.

## Memory explained

1. **Profile**: explicit identity, role, tone, instructions, voice delivery and
   permissions. This defines how the companion should behave.
2. **Conversation memory**: local SQLite history with user/assistant roles,
   timestamps, searchable text and separate confirmed facts. Facts refer to the
   user message that established them. Editing a fact through the UI creates a
   user-sourced memory entry; it does not fabricate an assistant recollection.
3. **Reply context**: a bounded selection of recent and relevant older messages,
   confirmed facts and fresh observations is supplied for each reply. The entire
   archive is not sent every time. Memory does not retrain model weights or
   guarantee perfect recall. The new page makes the stored evidence inspectable.
4. **Diagnostic archive**: transcripts, events and WAV recordings remain separate
   from recall. Clearing a fact does not erase those records. Existing export
   controls remain available.

The existing personality backup currently covers name, role and custom
instructions only; it is not a full voice/memory/permissions backup.

## Local action slice

Exact English requests can bypass reply generation:

- `Calculate 245 * 18` or `What is 245 times 18?`
- `Open calculator and calculate 245 * 18`
- `Start a 5 minute timer`
- `Open calculator`, `Open notepad`, `Open file explorer`

Arithmetic uses a restricted AST interpreter for numeric +, -, *, / and
parentheses. Names, function calls, exponentiation, division by zero, malformed
expressions and excessive values/complexity are rejected. No Python eval or
user-generated shell command is used. Other languages or phrasings can still
use the reply model and supported tools; direct command routing is not claimed
to be a universal multilingual parser. Speech recognition and synthesis still
use their services even when reply generation is skipped.

Calculator interaction uses Windows UI Automation InvokePattern on specific
Calculator controls. The adapter checks the target process and reads
CalculatorResults. A live check entered 245 × 18 and read `Display is 4,410`.
The app reports Calculator verification only when that display matches the
independently computed result. The first adapter supports simple two-operand
numeric expressions on an English-labelled Windows Calculator. More complex
arithmetic can run locally, with an explicit message that Calculator display was
not verified. It does not send global keystrokes to whichever app has focus.

One-shot timers persist locally and are claimed once when due. A background
poll keeps SQLite work off the Tk UI thread. A bubble notification waits while
the character is talking/capturing/thinking. Keep Setta running for timely
notifications; overdue timers can be claimed after restart. This is a visual
notification, not a system alarm service, and claimed status is not proof that
the user saw it. The existing recurring reminders remain separate.

## Storage

| Item | Absolute path |
|---|---|
| Current profile | `D:\projects codes\PROJECT SETTA\config\amma.json` |
| Chat history and confirmed facts | `D:\projects codes\PROJECT SETTA\data\memory\companion.sqlite` |
| One-shot timers | `D:\projects codes\PROJECT SETTA\data\memory\timers.sqlite` |
| Diagnostic transcripts, events and audio | `D:\projects codes\PROJECT SETTA\data\conversation-archive` |
| Profile & Memory page | `D:\projects codes\PROJECT SETTA\src\modern_hub.py` |
| Profile validation and prompt | `D:\projects codes\PROJECT SETTA\src\character_profile.py` |
| Local action parser and arithmetic | `D:\projects codes\PROJECT SETTA\src\local_actions.py` |
| Calculator adapter | `D:\projects codes\PROJECT SETTA\tools\calculator-action.ps1` |
| Timer storage | `D:\projects codes\PROJECT SETTA\src\local_timers.py` |

## Verification

176 regression tests passed on the final implementation. Tests cover arithmetic safety,
no-provider direct answers with preserved memory, timer persistence/one-shot
firing, disabled permissions, profile field preservation and native CTk
navigation. The actual native memory form saved a user-sourced Physics fact in
temporary test storage. No real user memories were deleted by verification.

An older camera cleanup regression fixture was updated to target the current
analysis worker, which now owns detectors; camera runtime code was not changed
to satisfy that fixture. Actual Calculator UI interaction was verified; a full
spoken turn using the new commands still needs the user's microphone check.

## Future companion profiles

Names and roles are editable now. Partner, friend, long-distance and remembrance
use cases are future product directions, not enabled account/profile types.
Before adding a profile switcher, isolate each companion's memory, journal,
face references, voice consent/configuration and permissions under a stable
profile ID. Do not implement presets by renaming Amma while sharing all history.
Role-aware address terms and permissions are early building blocks; complete
template systems and shared-person access still require design and testing.

Keep the digital companion's identity honest and its memories sourced. A profile
cannot establish another person's real thoughts, feelings or past experiences.
The expressive voice experiments and proactive study policy remain separate
future work, as documented in the research report.
