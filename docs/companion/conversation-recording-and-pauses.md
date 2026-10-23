# Conversation archive and sentence capture

All new submitted turns through the Amma text chat, native voice and hands-free bridge use LiveConversation's local diagnostic journal. Existing conversational memory remains data/memory/companion.sqlite. No past raw audio can be recovered retroactively.

Exact archive locations:

- D:/projects codes/PROJECT SETTA/data/conversation-archive/events.sqlite — append-only session/turn IDs, UTC timestamps, transcription, input text, generated reply, stage errors, and streaming/browser playback markers.
- D:/projects codes/PROJECT SETTA/data/conversation-archive/audio/TURN-ID/input.wav — exact uploaded microphone audio, including pauses.
- The same turn directory stores native synthesized WAV chunks. Browser streaming completion and errors are recorded, but the outgoing PCM stream itself is not archived.
- D:/projects codes/PROJECT SETTA/runtime/reply-provider-error.json — safe most-recent provider status and quota diagnostics, without raw provider error bodies or keys.

Generated replies remain in the journal even if interruption removes them from conversational recall. Generated, streamed and acknowledged-playback stages are distinct. Interrupted browser playback can be partial. Input audio is saved before transcription, so failed/empty transcription can be investigated. Error records contain exception types, not raw exception messages that might leak credentials. Files are local and ignored by Git. They are not encrypted by this implementation; no automatic expiry is applied. Stopping the microphone stops capture; unsubmitted browser buffers are discarded and are not archived. Journal failures propagate rather than silently claiming a turn was saved.

Browser pause detection now waits 1.5 seconds by default, with 2.2 seconds and manual Send now options. Manual mode is most reliable for long pauses or soft speech. Threshold was lowered from RMS .025 to .018 and duplicate pre-roll frames were removed. Native microphone waits 1.5 seconds, up from .45 seconds. Both modes allow up to 27 seconds; hitting that limit archives/transcribes the captured segment and asks for shorter turns rather than answering an unfinished sentence. The finite limit respects the current speech API request limit; longer continuous dictation needs a separate streaming/chunking design.

The pause tests use synthetic frames: a 0.9-second internal silence followed by speech must stay in the same turn; final silence sends once; manual mode does not send until the button is pressed. These checks do not establish microphone accuracy on the user's hardware. If the audio file contains the whole sentence but transcription is incomplete, investigate STT next using the same-recording comparison tools. If the WAV is cut off, investigate endpointing/microphone capture.
