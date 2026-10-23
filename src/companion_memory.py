"""Local, source-labelled mother-chat memory. No model or microphone dependency."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CompanionMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL,
                    text TEXT NOT NULL, language TEXT, created_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'mother_chat', external_id TEXT UNIQUE
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
                    text, content='messages', content_rowid='id', tokenize='unicode61'
                );
                CREATE TRIGGER IF NOT EXISTS messages_insert AFTER INSERT ON messages BEGIN
                    INSERT INTO message_search(rowid,text) VALUES(new.id,new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS messages_delete AFTER DELETE ON messages BEGIN
                    INSERT INTO message_search(message_search,rowid,text) VALUES('delete',old.id,old.text);
                    DELETE FROM facts WHERE source_message_id=old.id;
                END;
                CREATE TABLE IF NOT EXISTS facts (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, source_message_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_message(self, session: str, role: str, text: str, language: str | None = None,
                    external_id: str | None = None) -> int:
        if role not in ('user', 'assistant') or not text.strip() or not session:
            raise ValueError('A session, user/assistant role and nonempty text are required')
        with self._db() as db:
            if external_id is not None:
                existing = db.execute('SELECT * FROM messages WHERE external_id=?', (external_id,)).fetchone()
                if existing:
                    if (existing['session'], existing['role'], existing['text']) != (session, role, text):
                        raise ValueError('Message ID already belongs to different content')
                    return existing['id']
            return db.execute('INSERT INTO messages(session,role,text,language,created_at,external_id) '
                              'VALUES(?,?,?,?,?,?)',
                              (session, role, text, language, utc_now(), external_id)).lastrowid

    def sessions(self, limit=60):
        with self._db() as db:
            return [dict(row) for row in db.execute("""SELECT session, MIN(created_at) AS started_at,
                MAX(created_at) AS ended_at, COUNT(*) AS messages,
                (SELECT text FROM messages first WHERE first.session=m.session AND first.role='user' ORDER BY id LIMIT 1) AS title
                FROM messages m GROUP BY session ORDER BY MAX(id) DESC LIMIT ?""", (limit,))]

    def recent(self, limit: int = 20, session: str | None = None) -> list[dict]:
        if not 1 <= limit <= 200:
            raise ValueError('Limit must be between 1 and 200')
        where, args = (' WHERE session=?', [session]) if session is not None else ('', [])
        with self._db() as db:
            rows = db.execute('SELECT * FROM messages' + where + ' ORDER BY id DESC LIMIT ?',
                              [*args, limit]).fetchall()
        return [dict(row) for row in reversed(rows)]

    def search(self, query: str, limit: int = 8) -> list[dict]:
        if not 1 <= limit <= 50:
            raise ValueError('Search limit must be between 1 and 50')
        # Quote user terms, so punctuation and FTS operators cannot change query semantics.
        terms = [term.strip() for term in query.split() if any(c.isalnum() for c in term)][:20]
        if not terms:
            return []
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        with self._db() as db:
            rows = db.execute('SELECT m.* FROM message_search s JOIN messages m ON m.id=s.rowid '
                              'WHERE message_search MATCH ? ORDER BY rank LIMIT ?', (expression, limit)).fetchall()
        return [dict(row) for row in rows]

    def remember(self, key: str, value: str, source_message_id: int) -> None:
        """Only explicit user-confirmed facts belong here, never inferred moods."""
        if not key.strip() or not value.strip():
            raise ValueError('Fact key/value required')
        with self._db() as db:
            source = db.execute('SELECT role FROM messages WHERE id=?', (source_message_id,)).fetchone()
            if source is None or source['role'] != 'user':
                raise ValueError('Facts must reference a stored user message')
            db.execute('INSERT INTO facts(key,value,source_message_id,updated_at) VALUES(?,?,?,?) '
                       'ON CONFLICT(key) DO UPDATE SET value=excluded.value, '
                       'source_message_id=excluded.source_message_id,updated_at=excluded.updated_at',
                       (key, value, source_message_id, utc_now()))

    def facts(self) -> list[dict]:
        with self._db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM facts ORDER BY updated_at DESC LIMIT 100')]

    def forget_fact(self, key: str) -> None:
        with self._db() as db:
            db.execute('DELETE FROM facts WHERE key=?', (key,))

    def delete_message(self, message_id: int) -> None:
        with self._db() as db:
            db.execute('DELETE FROM messages WHERE id=?', (message_id,))

    def export(self, path: Path) -> None:
        with self._db() as db:
            messages = [dict(row) for row in db.execute('SELECT * FROM messages ORDER BY id')]
            facts = [dict(row) for row in db.execute('SELECT * FROM facts ORDER BY key')]
        Path(path).write_text(json.dumps({'messages': messages, 'facts': facts}, ensure_ascii=False, indent=2),
                              encoding='utf-8')
