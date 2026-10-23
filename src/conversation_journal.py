"""Append-only local diagnostic archive, separate from conversational recall."""
from datetime import datetime, timezone
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class ConversationJournal:
    def __init__(self, root: Path, session: str):
        self.root, self.session = root, session
        root.mkdir(parents=True, exist_ok=True)
        self.database = root/'events.sqlite'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time_utc TEXT, session TEXT, turn_id TEXT, stage TEXT, details TEXT)')

    def new_turn(self):
        return str(uuid4())

    def event(self, turn_id, stage, **details):
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            db.execute('INSERT INTO events(time_utc,session,turn_id,stage,details) VALUES(?,?,?,?,?)',
                (datetime.now(timezone.utc).isoformat(), self.session, turn_id, stage,
                 json.dumps(details, ensure_ascii=False)))

    def audio(self, turn_id, data, name='input.wav'):
        folder = self.root/'audio'/turn_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/name
        path.write_bytes(data)
        self.event(turn_id, 'audio_saved', path=str(path.resolve()), bytes=len(data))
