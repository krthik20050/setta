"""Measure real Tk callback latency using isolated data, including a busy database."""
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.companion_hub import CompanionHub, HubPreferences
from src.companion_memory import CompanionMemory
from src.local_reminders import LocalReminders
from src.paths import PROJECT_ROOT


def measure():
    parent = PROJECT_ROOT / 'runtime' / 'latency-check'
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as folder:
        base = Path(folder)
        root = tk.Tk()
        root.withdraw()
        memory = CompanionMemory(base/'chat.sqlite')
        reminders = LocalReminders(base/'reminders.sqlite')
        app = SimpleNamespace(root=root, character_profile=SimpleNamespace(name='Amma'),
            hub_preferences=HubPreferences(base/'settings.json'), reminders=reminders,
            voice_agent=SimpleNamespace(active=False, muted=True, stop=lambda: None),
            webcam=SimpleNamespace(status='Isolated check', face_lock=threading.Lock(), latest_face=None),
            _use_approved_face=tk.BooleanVar(root, True), _live_conversation=SimpleNamespace(memory=memory))
        for name in ('_exit_app', '_open_handsfree', '_trigger_walk', '_stop_walk'):
            setattr(app, name, lambda: None)
        app._play_mother = lambda *args: None
        app._submit_hub_chat = lambda text: None
        hub = CompanionHub(app)
        root.update()
        try:
            for number in range(80):
                memory.add_message('synthetic', 'user' if number % 2 else 'assistant',
                    f'Synthetic message {number}. ' + 'An ordinary conversation sentence. '*12)
            started = time.perf_counter()
            hub.show_page('Conversation')
            root.update_idletasks()
            history_ms = (time.perf_counter()-started)*1000
            # An exclusive write replicates a concurrent memory writer/disk stall.
            locked = threading.Event()
            def hold_database():
                db = sqlite3.connect(memory.path)
                try:
                    db.execute('BEGIN EXCLUSIVE')
                    locked.set()
                    time.sleep(.65)
                    db.rollback()
                finally:
                    db.close()
            worker = threading.Thread(target=hold_database)
            worker.start()
            if not locked.wait(2):
                raise RuntimeError('Database lock fixture did not start')
            gaps = []
            previous = time.perf_counter()
            def heartbeat():
                nonlocal previous
                stamp = time.perf_counter()
                gaps.append((stamp-previous)*1000)
                previous = stamp
                root.after(20, heartbeat)
            root.after(20, heartbeat)
            root.after(40, hub._refresh_history)
            root.after(1100, root.quit)
            root.mainloop()
            worker.join()
            durations = []
            for page in ('Home', 'Reminders', 'Camera', 'Connections', 'Settings', 'Conversation'):
                start = time.perf_counter()
                hub.show_page(page)
                root.update_idletasks()
                durations.append((time.perf_counter()-start)*1000)
            return {'chat_navigation_ms': round(history_ms, 1),
                    'max_heartbeat_gap_under_database_lock_ms': round(max(gaps), 1),
                    'max_page_switch_ms': round(max(durations), 1)}
        finally:
            hub.close()
            while hub._io.alive:
                time.sleep(.005)
            root.destroy()


if __name__ == '__main__':
    result = measure()
    print(json.dumps(result, indent=2))
    if '--check' in sys.argv and result['max_heartbeat_gap_under_database_lock_ms'] > 200:
        raise SystemExit('UI blocked for over 200 ms while chat storage was busy')
