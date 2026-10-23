# Record once and compare

Start the local recording page with `powershell -NoProfile -ExecutionPolicy Bypass -File tools/start-stt-test.ps1` from the project directory. The page is http://127.0.0.1:8771/record-stt.html. Microphone access starts only when Record is clicked. No audio is sent from this page.

Record 8–12 phrases, each under 15 seconds. Include Malayalam, English, Hindi, Malayalam-English switching, names, numbers, and a quiet phrase. Write the exact spoken words next to each. Play back and discard unusable sessions by reloading before export. Export all recordings to amma-stt-recordings.json; it contains private audio encoded as base64. Keep the original export for repeatable comparisons.

Run `python tools/voice/compare_stt.py "C:/path/to/amma-stt-recordings.json"`. This explicitly uploads every recording to Sarvam v3/v4 and Groq Whisper Large v3/Turbo using the existing project keys. Normal provider usage applies. Missing keys or unsupported models appear as failures, not winning results. No production model setting changes.

Outputs are under data/stt-comparison/TIMESTAMP/results.json and compare.html, ignored by Git. Each row includes an identical input SHA256, model, output, detected language when returned, HTTP status and elapsed request time. Raw provider error bodies and keys are excluded. Review missing/changed words, names, numbers and language switches. Manglish expectations require manual comparison against native-script outputs; do not interpret different scripts as word recognition errors. A single request time is not a statistically reliable model ranking; repeat the same dataset and compare medians after checking errors.

The archived teaching clips can help test Malayalam transcription, but cannot establish performance on Karthik's microphone, accent, mixed speech or room noise. These new recordings are the main evaluation set.
