"""Exercise actual CTk navigation containers, not just the selected-page variable."""
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.companion_hub import CompanionHub, HubPreferences
from src.local_reminders import LocalReminders
from src.paths import PROJECT_ROOT
from src.character_profile import CharacterProfile
from src.companion_memory import CompanionMemory


class NavigationTests(unittest.TestCase):
    def test_each_sidebar_button_exclusively_displays_its_real_page(self):
        scratch = PROJECT_ROOT / 'runtime' / 'navigation-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            base = Path(directory)
            root = tk.Tk()
            root.withdraw()
            app = SimpleNamespace(root=root, character_profile=CharacterProfile({'name':'Amma'}),
                hub_preferences=HubPreferences(base/'settings.json'),
                reminders=LocalReminders(base/'reminders.sqlite'), voice_agent=None,
                webcam=SimpleNamespace(status='Test only', face_lock=threading.Lock(), latest_face=None),
                _use_approved_face=tk.BooleanVar(root, True),
                _live_conversation=SimpleNamespace(memory=CompanionMemory(base/'memory.sqlite')),
                _exit_app=lambda: None, _open_handsfree=lambda: None,
                _trigger_walk=lambda: None, _stop_walk=lambda: None,
                _play_mother=lambda *args: None)
            hub = None
            try:
                with patch('src.modern_hub.DATA_DIR', base):
                    hub = CompanionHub(app)
                root.update()
                hub.fact_key.insert(0,'favourite_subject')
                hub.fact_value.insert(0,'Physics')
                hub.save_memory_fact()
                deadline=time.monotonic()+3
                while not app._live_conversation.memory.facts() and time.monotonic()<deadline:
                    root.update(); time.sleep(.02)
                self.assertEqual(app._live_conversation.memory.facts()[0]['value'],'Physics')
                routes = ['Home', 'Conversation', 'Reminders', 'Camera', 'Connections', 'Profile & Memory', 'Settings']
                for selected in ['Conversation', *routes, 'Conversation', *reversed(routes)]:
                    with self.subTest(page=selected):
                        hub.nav[selected].invoke()
                        root.update()
                        self.assertEqual(hub.active_page, selected)
                        self.assertEqual([name for name, host in hub.page_hosts.items()
                                          if host.winfo_ismapped()], [selected])
                        self.assertEqual([name for name, page in hub.pages.items()
                                          if page.winfo_viewable()], [selected])
                        self.assertTrue(hub.pages[selected].winfo_width() > 200)
                        self.assertTrue(hub.pages[selected].winfo_height() > 100)
            finally:
                if hub:
                    hub.close()
                    deadline = time.monotonic()+3
                    while hub._io.alive and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertFalse(hub._io.alive)
                root.destroy()
