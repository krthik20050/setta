"""Local timestamped app/window history, without screenshots or file access."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading
import time

from .companion_context import Observation
from .desktop_context import foreground_window


def desktop_question(text: str) -> bool:
    return bool(re.search(r'\b(working on|work on|doing on|what (?:am|was) i doing|my screen|my desktop|which app|what app|'
                          r'active app|active window|open on|screenil|enth.*chey|njan.*chey)\b|'
                          r'\u0d38\u0d4d\u0d15\u0d4d\u0d30\u0d40\u0d28|\u0915\u093e\u092e|\u0938\u094d\u0915\u094d\u0930\u0940\u0928', text, re.I))


class DesktopActivity:
    def __init__(self, path: Path, settings: dict, reader=None):
        self.path = path
        self.settings = settings
        self.retention_days = max(1,min(30,int(settings.get('desktop_history_days',7))))
        self.reader = reader or (lambda: foreground_window(skip_own=True,
                                  include_title=settings.get('window_title', False)))
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest = None
        self._thread = None
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, '
                       'app TEXT NOT NULL,title TEXT NOT NULL,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL)')

    @contextmanager
    def _db(self):
        connection = sqlite3.connect(self.path, timeout=2)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def poll(self):
        window = self.reader()
        if not window:
            return
        stamp = datetime.now(timezone.utc).isoformat()
        item = {'app': window['app'], 'title': window.get('title', ''), 'observed_at': stamp}
        with self._lock:
            self._latest = (item, time.monotonic())
            with self._db() as db:
                last = db.execute('SELECT id,app,title FROM activity ORDER BY id DESC LIMIT 1').fetchone()
                if last and last[1:] == (item['app'], item['title']):
                    db.execute('UPDATE activity SET last_seen=? WHERE id=?', (stamp,last[0]))
                else:
                    db.execute('INSERT INTO activity(app,title,first_seen,last_seen) VALUES(?,?,?,?)',
                               (item['app'],item['title'],stamp,stamp))
                db.execute("DELETE FROM activity WHERE julianday(last_seen) < julianday('now',?)",
                           (f'-{self.retention_days} days',))
                db.execute('DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 5000)')

    def observations(self):
        now = time.monotonic()
        with self._lock:
            result = []
            if self._latest:
                item, observed = self._latest
                if now-observed <= 5:
                    result.append(Observation('foreground_window',json.dumps(item),
                                               'windows_foreground_observation',1,observed,5))
            with self._db() as db:
                db.row_factory = sqlite3.Row
                rows = [dict(row) for row in db.execute(
                    'SELECT app,title,first_seen,last_seen FROM activity ORDER BY id DESC LIMIT 8')]
            result.append(Observation('recent_desktop_activity',json.dumps(rows),
                                      'local_timestamped_app_history',1,now,5))
            return result

    def start(self):
        if not self.settings.get('foreground_app',False):
            return
        if self._thread and self._thread.is_alive(): return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run,daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.poll()
            except (OSError, sqlite3.Error):
                pass  # Unavailable observations remain absent, never fabricated.
            self._stop.wait(2)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread(): self._thread.join(timeout=.3)
