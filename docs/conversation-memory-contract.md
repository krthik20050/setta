# Setta conversation and memory contract

Scope agreed 2026-10-20: mother chat only. Sarvam owns language detection, dialogue wording, speech recognition, synthesis and the cloned voice; those files are being developed in another chat and were not edited here. Desktop control is optional and only follows a user request and action-specific authorization. No email, WhatsApp, Telegram or desktop-history connector is enabled by this work.

## Conversation flow
Sarvam recognized turn -> memory/context retrieval -> timing/decision layer -> Sarvam dialogue -> presented text/audio -> memory completion. The avatar receives expression events separately. Laya may choose fixed decisions (quiet/check-in/help/offer break); Sarvam handles what to say and in which language. A decision model does not replace conversation, identity recognition or facial analysis.

## Implemented independent modules
- src/companion_memory.py: SQLite chat archive with Unicode FTS5 lexical search, timestamps, roles, sessions, provenance, optional deduplication IDs, explicit facts, fact correction, deletion and JSON export. All connections close on success/error. Default integration path should be data/memory/companion.sqlite, which is ignored by Git. No database of actual user conversations is created until the integration is used.
- src/companion_context.py: bounded recent history, cross-session recent messages, relevant older messages, confirmed facts and fresh timestamped observations. Observation metadata stays in working context; raw camera frames/face embeddings are not stored here. Future and stale observations are excluded. Long records are labelled when clipped for context; full text remains in the archive.
- ConversationSession.turn: accepts an injected Sarvam text adapter, stores user text, retrieves prior context before saving the current message, and stores successful assistant replies. Provider failures do not become invented replies. One instance should be driven serially by the conversation worker, not by parallel voice turns.
- InteractionTiming: no check-in during user speech, quiet mode or a pending reply; minimum 120-second proactive cooldown; low-confidence context/absent user suppresses proactive check-ins. Audio starts muted. Desktop action permission requires both explicit user request and action authorization. These gates need wiring into the runtime; they do not independently cancel an existing audio stream or desktop tool.

## Adapter contract for the Sarvam chat
The adapter is respond(text: str, language: str, context: dict) -> str. It must keep the original recognized text separate from retrieved context, apply the language rules already owned by SarvamConversation, quote memory as evidence instead of treating it as system instructions, and preserve the user's correction over older memory. It must not claim external message access when context.missing_sources includes external_messages.

Example (integration snippet, not automatic wiring):

    from src.paths import DATA_DIR
    from src.companion_memory import CompanionMemory
    from src.companion_context import ConversationSession
    memory = CompanionMemory(DATA_DIR / 'memory' / 'companion.sqlite')
    session = ConversationSession(memory, stable_session_id)
    reply = session.turn(turn.text, turn.language, sarvam_text_adapter,
                         observations=fresh_camera_observations)

To show recent mother-chat messages, use memory.recent(limit=20), including dates/roles. Do not ask a language model to invent a transcript. To explicitly remember a preference, save the user's confirmation message ID then call memory.remember(key, value, source_message_id). Do not automatically store model-inferred emotions as confirmed facts. A fact correction replaces the active value; original source messages remain unless the user deletes them. Deleting a source message removes its dependent facts and full-text-search entry.

## What good memory means
Archive the actual conversations and retrieve a small relevant subset each turn. Do not replay the entire archive into every model request. Never promise perfect recall of everything the user did. This slice is lexical retrieval, not semantic embeddings, automatic summaries, a knowledge graph or automatic topic resolution. Exact and shared-keyword recall plus recent history work now; paraphrase-heavy retrieval, date-filtering and summary/reconsolidation need a later evaluated layer. FTS Unicode tokenization is not a Malayalam morphological model.

Data is local SQLite/JSON, not application-level encrypted. Exported JSON includes chat text. The database is unrelated to Codex's own memory folder. No files under Codex memories were written.

## Facial context
Identity: who is present, match confidence, track ID and frame quality. Behaviour: eye-closure duration, possible yawn, gaze/head direction. Interpretations: uncertain hypotheses that should prompt a gentle question, not a stored diagnosis. Current Setta camera heuristics are not advanced emotion understanding. Multi-view enrollment and validated temporal classifiers remain required. Use timestamps and expire identity/cues when tracking is lost; a stale callback must not identify a new person.

## Timing and action rules to wire next
The dialogue worker should mark user_speaking/reply_in_progress, stop pending speech when interrupted, cancel a pending response when superseded, honor persistent mute, and update the proactive timestamp only after a check-in is actually shown. Unavailable camera or desktop context means unknown, not permission to guess. Mother chat memory alone does not provide desktop activity or external message history.

## Verification
Tests cover restart persistence, source labels, Unicode search, query punctuation, fact corrections, deletion, duplicate IDs/conflicting content, export, observation expiry, failed provider turns and timing/action gates. Tests use a temporary database under runtime/memory-tests and do not access microphone, call Sarvam or create real user history. Existing Sarvam tests remain unchanged. The live avatar/audio process has not been restarted or unmuted.

## Next concrete integration
Wire the existing Sarvam worker to ConversationSession through the adapter above, add memory review/delete controls, and pass fresh face observations into context. Run a two-session conversation where an explicitly confirmed preference is recalled after restart, then corrected and forgotten. Verify microphone interruption, real provider response language, mute and actual recall separately from the unit-test evidence.
