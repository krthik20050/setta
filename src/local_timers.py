"""Persistent one-shot timers. Fired once while the desktop app is running."""
from contextlib import closing
import sqlite3
import time
from pathlib import Path


class LocalTimers:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS timers(id INTEGER PRIMARY KEY,title TEXT,due REAL,fired INTEGER DEFAULT 0)')

    def create(self,seconds,title='Your timer is finished',now=None):
        if isinstance(seconds,bool): raise ValueError('Use a timer from one second to 24 hours')
        seconds=float(seconds)
        if not 1<=seconds<=86400: raise ValueError('Use a timer from one second to 24 hours')
        with closing(sqlite3.connect(self.path)) as db,db:
            cursor=db.execute('INSERT INTO timers(title,due) VALUES(?,?)',(title,(time.time() if now is None else now)+seconds))
            return cursor.lastrowid

    def due(self,now=None):
        with closing(sqlite3.connect(self.path,timeout=2)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT id,title FROM timers WHERE fired=0 AND due<=?',(time.time() if now is None else now,)).fetchall()
            db.executemany('UPDATE timers SET fired=1 WHERE id=?',[(row[0],) for row in rows])
            return [{'id':row[0],'title':row[1]} for row in rows]
