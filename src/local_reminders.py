"""Durable local interval reminders; confirmations are user reports, not proof.

``due`` claims each occurrence once. Pending occurrences remain visible through
``list`` after restart; polling never repeats them or replays missed intervals.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as datetime_timezone
import json
import math
import re
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _zone(name):
    # Windows commonly has no IANA database. Kolkata has no DST and this
    # fallback preserves the promised contemporary Indian wall-clock schedule.
    if name == 'Asia/Kolkata':
        return datetime_timezone(timedelta(hours=5, minutes=30))
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError('Choose a supported timezone') from None


def _clock(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('Use a time in HH:MM format')
    hours, minutes = map(int, value.split(':'))
    return hours * 60 + minutes


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
        raise ValueError('Give the reminder a name of 1 to 160 characters')
    return value.strip()


def _minutes(value):
    if isinstance(value, bool):
        raise ValueError('Interval must be between 1 and 1440 minutes')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('Interval must be between 1 and 1440 minutes') from None
    if not math.isfinite(number) or not 1 <= number <= 1440:
        raise ValueError('Interval must be between 1 and 1440 minutes')
    return number


def _now(value):
    number = time.time() if value is None else float(value)
    if not math.isfinite(number):
        raise ValueError('Time must be finite')
    return number


class LocalReminders:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                interval_minutes REAL NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                next_due REAL NOT NULL, pending INTEGER NOT NULL DEFAULT 0,
                last_prompted REAL, last_ack TEXT, last_ack_at REAL)''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(reminders)')}
            if 'archived' not in columns:
                db.execute('ALTER TABLE reminders ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')
            db.execute('''CREATE TABLE IF NOT EXISTS reminder_history (
                id INTEGER PRIMARY KEY, reminder_id INTEGER, title TEXT NOT NULL,
                action TEXT NOT NULL, at REAL NOT NULL, source TEXT NOT NULL,
                details TEXT NOT NULL)''')
            if 'one_shot' not in columns:
                db.execute('ALTER TABLE reminders ADD COLUMN one_shot INTEGER NOT NULL DEFAULT 0')
            db.execute('CREATE INDEX IF NOT EXISTS reminder_history_lookup ON reminder_history(reminder_id,id)')
            db.execute('CREATE TABLE IF NOT EXISTS reminder_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_water(self, interval_minutes=60, now=None):
        """Create a reminder whose first check-in is one interval from now."""
        return self.create('Did you drink some water?', interval_minutes, kind='water', now=now)

    def create(self, title, interval_minutes=60, kind='custom', now=None):
        title = _title(title)
        if kind not in {'water', 'custom'}:
            raise ValueError('Choose water or custom reminder')
        interval = _minutes(interval_minutes)
        stamp = _now(now)
        with self._db() as db:
            cursor = db.execute('''INSERT INTO reminders
                (kind,title,interval_minutes,next_due) VALUES (?,?,?,?)''',
                (kind, title, interval, stamp + interval * 60))
            reminder_id = cursor.lastrowid
            self._record(db, reminder_id, title, 'create', stamp, interval_minutes=interval)
        return self.get(reminder_id)

    def create_once(self, title, delay_seconds, now=None):
        title, stamp = _title(title), _now(now)
        seconds = float(delay_seconds)
        if not math.isfinite(seconds) or not 1 <= seconds <= 86400:
            raise ValueError('Choose a delay from one second to 24 hours')
        with self._db() as db:
            cursor = db.execute("INSERT INTO reminders(kind,title,interval_minutes,next_due,one_shot) VALUES ('custom',?,?,?,1)",
                                (title, max(1, seconds / 60), stamp + seconds))
            identifier = cursor.lastrowid
            self._record(db, identifier, title, 'create_once', stamp, delay_seconds=seconds)
        return self.get(identifier)

    def list(self, include_archived=False):
        with self._db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM reminders WHERE archived=0 OR ? ORDER BY id', (int(include_archived),))]

    @staticmethod
    def _record(db, reminder_id, title, action, stamp, source='user', **details):
        db.execute('''INSERT INTO reminder_history
            (reminder_id,title,action,at,source,details) VALUES (?,?,?,?,?,?)''',
            (reminder_id, title, action, stamp, source, json.dumps(details)))

    def history(self, reminder_id=None, limit=50):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError('History limit must be between 1 and 200')
        with self._db() as db:
            rows = db.execute('''SELECT * FROM reminder_history
                WHERE (? IS NULL OR reminder_id=?) ORDER BY id DESC LIMIT ?''',
                (reminder_id, reminder_id, limit)).fetchall()
            return [{**dict(row), 'details': json.loads(row['details'])} for row in rows]

    def update(self, reminder_id, title, interval_minutes, now=None):
        title, interval, stamp = _title(title), _minutes(interval_minutes), _now(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reminders WHERE id=? AND archived=0', (reminder_id,)).fetchone()
            if row is None:
                return None
            db.execute('''UPDATE reminders SET title=?,interval_minutes=?,pending=0,next_due=?
                WHERE id=?''', (title, interval, stamp + interval * 60, reminder_id))
            self._record(db, reminder_id, title, 'edit', stamp, interval_minutes=interval)
        return self.get(reminder_id)

    def archive(self, reminder_id, now=None):
        stamp = _now(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reminders WHERE id=? AND archived=0', (reminder_id,)).fetchone()
            if row is None:
                return False
            db.execute('UPDATE reminders SET archived=1,enabled=0,pending=0 WHERE id=?', (reminder_id,))
            self._record(db, reminder_id, row['title'], 'archive', stamp)
            return True

    def quiet_hours(self):
        with self._db() as db:
            return self._quiet_settings(db)

    @staticmethod
    def _quiet_settings(db):
        row = db.execute("SELECT value FROM reminder_settings WHERE key='quiet_hours'").fetchone()
        return json.loads(row['value']) if row else dict(enabled=False, start='22:00', end='08:00', timezone='Asia/Kolkata')

    def set_quiet_hours(self, enabled, start='22:00', end='08:00', timezone='Asia/Kolkata', now=None):
        if not isinstance(enabled, bool):
            raise ValueError('Enabled must be a boolean')
        if _clock(start) == _clock(end):
            raise ValueError('Quiet hours must have different start and end times')
        _zone(timezone)
        settings = dict(enabled=enabled, start=start, end=end, timezone=timezone)
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO reminder_settings VALUES ('quiet_hours',?)", (json.dumps(settings),))
            self._record(db, None, 'Quiet hours', 'quiet_hours', _now(now), **settings)
        return settings

    @staticmethod
    def _quiet_end(settings, stamp):
        if not settings['enabled']:
            return None
        local = datetime.fromtimestamp(stamp, _zone(settings['timezone']))
        start, end = _clock(settings['start']), _clock(settings['end'])
        minute = local.hour * 60 + local.minute
        inside = start <= minute < end if start < end else minute >= start or minute < end
        if not inside:
            return None
        result = local.replace(hour=end // 60, minute=end % 60, second=0, microsecond=0)
        if start > end and minute >= start:
            result += timedelta(days=1)
        return result.timestamp()

    def is_quiet(self, now=None):
        return self._quiet_end(self.quiet_hours(), _now(now)) is not None

    def get(self, reminder_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM reminders WHERE id=?', (reminder_id,)).fetchone()
            return dict(row) if row else None

    def set_enabled(self, reminder_id, enabled, now=None):
        """Pause cancels the pending check-in; resume starts a fresh interval."""
        stamp = _now(now)
        if not isinstance(enabled, bool):
            raise ValueError('Enabled must be a boolean')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reminders WHERE id=? AND archived=0', (reminder_id,)).fetchone()
            changed = db.execute('''UPDATE reminders SET enabled=?, pending=0,
                next_due=? + interval_minutes*60 WHERE id=? AND enabled!=? AND archived=0''',
                (int(enabled), stamp, reminder_id, int(enabled)))
            if changed.rowcount:
                self._record(db, reminder_id, row['title'], 'resume' if enabled else 'pause', stamp)
        return self.get(reminder_id)

    def due(self, now=None):
        """Atomically claim new due check-ins, once each until acknowledged."""
        stamp = _now(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            settings = self._quiet_settings(db)
            rows = db.execute('''SELECT * FROM reminders WHERE enabled=1
                AND archived=0 AND pending=0 AND next_due<=? ORDER BY next_due,id''', (stamp,)).fetchall()
            claimed = []
            for row in rows:
                quiet_end = self._quiet_end(settings, stamp) or self._quiet_end(settings, row['next_due'])
                if quiet_end is not None:
                    next_due = max(stamp, quiet_end) + row['interval_minutes'] * 60
                    db.execute('UPDATE reminders SET next_due=? WHERE id=?', (next_due, row['id']))
                    self._record(db, row['id'], row['title'], 'quiet_deferred', stamp,
                                 source='scheduler', next_due=next_due)
                    continue
                db.execute('UPDATE reminders SET pending=1,last_prompted=? WHERE id=?',
                           (stamp, row['id']))
                self._record(db, row['id'], row['title'], 'due', stamp, source='scheduler')
                claimed.append({**dict(row), 'pending': 1, 'last_prompted': stamp})
            return claimed

    def ack(self, reminder_id, action='done', now=None, snooze_minutes=5):
        """Record done/skip or defer. Duplicate/stale acknowledgments do nothing."""
        if action not in {'done', 'skip', 'snooze'}:
            raise ValueError('Choose done, skip, or snooze')
        snooze = _minutes(snooze_minutes) if action == 'snooze' else None
        stamp = _now(now)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reminders WHERE id=?', (reminder_id,)).fetchone()
            if row is None or not row['enabled'] or not row['pending']:
                return False
            delay = snooze if snooze is not None else row['interval_minutes']
            db.execute('''UPDATE reminders SET pending=0,next_due=?,last_ack=?,last_ack_at=?
                WHERE id=?''', (stamp + delay * 60, action, stamp, reminder_id))
            if row['one_shot'] and action != 'snooze':
                db.execute('UPDATE reminders SET enabled=0 WHERE id=?', (reminder_id,))
            self._record(db, reminder_id, row['title'], action, stamp,
                         source='user_report' if action == 'done' else 'user', delay_minutes=delay)
            return True
