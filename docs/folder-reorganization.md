# Folder reorganization — 2026-10-20

Project root: `D:\projects codes\PROJECT SETTA`.

- Application code remains under `src/`, with centralized paths in `src/paths.py`.
- Private credentials go in the root `.env`, which now exists with blank entries and is loaded by `setta.py`. `.env.example` is the safe template. Existing shell variables win; no keys were invented or copied from elsewhere.
- MediaPipe models are in `assets/models/`. Mother source artwork moved into `assets/mother/artwork/`; sound files into `assets/sounds/`; sound assignments into `config/sounds.json`.
- Private face embeddings moved intact into `data/known_faces/`. New camera registrations use this location.
- Existing logs and PID moved into `runtime/`. `tools/start.ps1` uses this location for future background launches and avoids a second launch when the recorded process still exists.
- Voice tools moved to `tools/voice/`; voice documentation to `docs/voice/`; companion research to `docs/companion/`; older plans and update notes to `docs/history/`.
- All voice recordings, approved references, source timestamps, checksums and review history retain their existing paths under `assets/mother/voice/`. No voice audio was deleted or reprocessed.
- Removed the unused cat `assets/spritesheet.webp`, nine root `row_*.png` files, and nine `assets/row_*.gif` files (19 images total), as requested.
- Two identical root model copies moved into `assets/models/`. The older copies immediately under `assets/` were locked by the existing process and remain temporarily. The new background launcher removes only hash-identical legacy copies after the old process exits. No running application was stopped.
- All mother source artwork and exported previews were retained. Hidden `.tools/` and `.superpowers/` remain tool-managed. Python caches are ignored generated files.

Detailed attempted moves and actual outcomes: `folder-reorganization-moves.json`. Removal summary and locked-file exception: `folder-reorganization-removals.json`. The model move journal records the original locked move attempt; the final model files were supplied by moving the verified identical root copies.

Verification: existing 18 regression tests passed after updating asset references. Final checks are recorded in `folder-reorganization-checks.json`. This does not prove camera/microphone hardware, provider calls, or the already-running process picked up the new source. Restart the companion when ready to use the new layout.

Dependencies: `requirements.txt` lists desktop source imports; `tools/voice/requirements.txt` lists optional audio tools. These are unpinned and have not been tested in a clean environment. No new provider integration or cloned voice was introduced by cleanup. Existing external Downloads sound paths in `config/sounds.json` and face-detection sound code were preserved; they remain portability limitations.

No Git commit or off-device backup was created. Documentation is saved locally; private credentials, media derivatives and face data are ignored by Git.
