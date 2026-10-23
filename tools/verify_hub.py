"""Exercise the real Tk hub with isolated local data and no camera/provider calls."""
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import tkinter as tk
import threading
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.companion_hub import CompanionHub, HubPreferences
from src.local_reminders import LocalReminders
from src.companion_memory import CompanionMemory
from src.paths import PROJECT_ROOT
from src.face_id import FaceID
import numpy as np


def main():
    scratch = PROJECT_ROOT / 'runtime' / 'hub-verification'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        root = tk.Tk()
        root.withdraw()
        calls = []
        def until(predicate):
            deadline = time.monotonic() + 3
            while not predicate() and time.monotonic() < deadline:
                root.update()
                time.sleep(.005)
            assert predicate(), 'Asynchronous UI operation did not finish'
        try:
            base = Path(folder)
            memory = CompanionMemory(base / 'memory.sqlite')
            app = SimpleNamespace(root=root, character_profile=SimpleNamespace(name='Amma'),
                hub_preferences=HubPreferences(base / 'settings.json'),
                reminders=LocalReminders(base / 'reminders.sqlite'),
                voice_agent=SimpleNamespace(active=False, muted=True, stop=lambda: calls.append('stop')),
                webcam=SimpleNamespace(status='Not started in verification', face_lock=threading.Lock(), latest_face=None),
                _use_approved_face=tk.BooleanVar(root, True),
                _live_conversation=SimpleNamespace(memory=memory))
            app.profile_path = base / 'amma.json'
            app.face_id = FaceID(base / 'faces', '')
            app.webcam.start = Mock(return_value=True)
            app.webcam.release = Mock()
            for method in ('_exit_app', '_open_handsfree', '_toggle_cam', '_register_current_face',
                           '_show_face_observations', '_trigger_walk', '_stop_walk'):
                setattr(app, method, lambda m=method: calls.append(m))
            app._play_mother = lambda state, message: calls.append(state)
            app._submit_hub_chat = lambda text: calls.append(('chat', text))
            hub = CompanionHub(app)
            root.update()
            for name in ('Home', 'Conversation', 'Reminders', 'Camera', 'Connections', 'Settings', 'Home'):
                hub.nav[name].invoke()
                root.update()
                assert hub.active_page == name
                visible = [key for key, page in hub.pages.items() if page.winfo_viewable()]
                assert visible == [name], f'Navigation to {name} left the wrong pages visible: {visible}'
                mapped_hosts = [key for key, host in hub.page_hosts.items() if host.winfo_ismapped()]
                assert mapped_hosts == [name], f'Wrong page container displayed: {mapped_hosts}'
            until(lambda: hub._feature_snapshot is not None)
            hub.habit_title.insert(0, 'Stretch')
            hub.save_habit()
            until(lambda: not hub._reminder_busy)
            until(lambda: any(r['title'] == 'Stretch' for r in hub._reminder_rows))
            habit = next(r for r in hub._reminder_rows if r['title'] == 'Stretch')
            hub.select_habit(f"{habit['id']} - Stretch")
            hub._selected_reminder = habit['id']
            hub.habit_action('toggle')
            until(lambda: not hub._reminder_busy)
            assert not app.reminders.get(habit['id'])['enabled']
            hub.quiet_enabled.set(True)
            hub.save_quiet()
            until(lambda: not hub._reminder_busy)
            assert app.reminders.quiet_hours()['enabled']
            hub.quiet_enabled.set(False)
            hub.save_quiet()
            until(lambda: not hub._reminder_busy)
            hub.habit_action('archive')
            until(lambda: not hub._reminder_busy)
            assert not app.reminders.list()
            assert app.reminders.history()
            from src.character_profile import CharacterProfile
            from src.profile_backup import export_profile
            CharacterProfile.save_personality({'name': 'Backup Amma', 'role': 'Mother', 'custom_instructions': 'Be gentle.'}, app.profile_path)
            backup = base / 'personality-backup.json'
            export_profile(backup, app.profile_path)
            CharacterProfile.save_personality({'name': 'Current Amma'}, app.profile_path)
            with patch('src.modern_hub.filedialog.askopenfilename', return_value=str(backup)):
                hub.import_personality()
            until(lambda: getattr(hub, '_import_fields', None) is not None)
            assert CharacterProfile.load(app.profile_path).name == 'Current Amma'
            hub.apply_personality_import()
            until(lambda: hub.profile_save_button.cget('state') == 'normal')
            assert CharacterProfile.load(app.profile_path).name == 'Backup Amma'
            assert hub._drop_ready, 'Native drag-and-drop could not initialize'
            hub.show_page('Camera')
            hub.enroll_name.delete(0, 'end')
            app.face_id.photo_sample = Mock(return_value=(np.arange(1, 17), np.full((70, 70, 3), 100, dtype=np.uint8)))
            photo_path = str(base / 'face sample.png')
            hub.drop_photo(SimpleNamespace(data=root.tk.call('list', photo_path)))
            assert not hub._enrolling
            assert hub._pending_photo == photo_path
            hub.enroll_name.insert(0, 'Father')
            hub.enroll_photo()
            assert hub._enrolling
            assert hub.enroll_name.cget('state') == 'disabled'
            until(lambda: not hub._enrolling)
            until(lambda: bool(hub._face_rows))
            assert hub._face_rows[0]['name'] == 'Father'
            assert hub._face_rows[0]['thumbnail']
            from PIL import Image
            portrait_path = base / 'chosen portrait.png'
            Image.new('RGB', (400, 600), '#356f97').save(portrait_path)
            previous_portrait = hub._face_rows[0]['thumbnail']
            with patch('src.modern_hub.filedialog.askopenfilename', return_value=str(portrait_path)):
                hub.choose_portrait('Father')
            until(lambda: hub._face_rows[0]['thumbnail'] != previous_portrait)
            assert app.face_id.list_faces()[0]['samples'] == 1
            assert hub._face_images
            assert not hub._people_edit

            assert hub.enrollment_progress.get() == 1
            app.face_id.photo_sample.assert_called_once_with(photo_path)
            app.face_id.photo_sample.side_effect = ValueError('No face')
            hub.enroll_photo(photo_path)
            until(lambda: not hub._enrolling)
            assert hub.enrollment_progress.get() == 0
            assert hub.photo_enroll_button.cget('state') == 'normal'
            app.face_id.remove_face('Father')
            hub._refresh_faces()
            until(lambda: hub._face_rows == [])
            for theme in ('Light', 'Dark', 'System', 'Light'):
                hub.set_theme(theme)
                assert hub.preferences.values['theme'] == theme.lower()
            hub.set_theme('Light')
            hub.theme_toggle.toggle()
            assert hub.preferences.values['theme'] == 'dark'
            hub.system_theme_control.toggle()
            assert hub.preferences.values['theme'] == 'system'
            assert hub.theme_toggle.cget('state') == 'disabled'
            hub.set_theme('Light')
            hub.prefill_message('Help me plan my day')
            assert hub.composer.get() == 'Help me plan my day'
            hub.composer.delete(0, 'end')
            hub.collect_faces.set(True)
            hub.toggle_face_candidates()
            assert not app.face_id.capture_candidates, 'Camera off must prevent collection'
            initial_id = hub.window.winfo_id()
            hub.show_page('Reminders')
            hub.toggle_water_setup()
            root.update()
            hub.interval.set('45')
            hub.interval_entry._entry.event_generate('<MouseWheel>', delta=120)
            root.update()
            assert hub.interval.get() == '46'
            hub.wheel_interval(SimpleNamespace(delta=-120))
            assert hub.interval.get() == '45'
            hub.interval.set('1')
            hub.adjust_interval(-1)
            assert hub.interval.get() == '1'
            hub.set_theme('Dark')
            assert hub.preferences.values['theme'] == 'dark'
            hub.set_theme('Light')
            hub.show_page('Camera')
            app.webcam.start.assert_not_called()
            hub.toggle_preview()
            assert hub._preview
            app.webcam.start.assert_called_once()
            hub.show_page('Home')
            assert not hub._preview
            app.webcam.release.assert_called_once()
            hub.profile_name.delete(0, 'end')
            hub.profile_name.insert(0, 'Mama')
            hub.profile_instructions.insert('1.0', 'Keep replies short and caring.')
            hub.save_profile()
            until(lambda: app.profile_path.exists() and app.character_profile.name == 'Mama')
            assert 'short and caring' in app.character_profile.instructions('en-IN')
            hub.hide()
            hub.show('Conversation')
            assert hub.window.winfo_id() == initial_id
            hub.composer.insert(0, 'Hello Amma')
            hub.send()
            hub.send()
            assert calls.count(('chat', 'Hello Amma')) == 1
            hub.receive_reply('Hello. How is your day?')
            assert not hub.pending and app.voice_agent.muted
            hub.add_message('Amma', 'സുഖമാണോ?')
            rendered = hub.transcript.get('1.0', 'end')
            assert not any('\u0d00' <= char <= '\u0d7f' for char in rendered)
            hub.set_script('Malayalam (native script)')
            assert 'സുഖമാണോ?' in hub.transcript.get('1.0', 'end')
            hub.set_script('Manglish (Latin letters)')
            hub.composer.insert(0, 'enroll my faces')
            hub.send()
            assert hub.active_page == 'Camera'
            hub.enroll_name.insert(0, 'Owner')
            hub.enroll_face()
            assert 'No fresh face' in hub.enrollment_status.get()
            hub.walk()
            assert '_trigger_walk' in calls
            hub.interval.set('1')
            hub.start_water()
            until(lambda: bool(app.reminders.list()))
            reminder = app.reminders.list()[-1]
            assert len(app.reminders.due(now=time.time() + 61)) == 1
            hub._request_snapshot()
            until(lambda: hub.reminder_status.get() == 'Did you drink some water?')
            assert hub.reminder_status.get() == 'Did you drink some water?'
            hub.ack('snooze')
            until(lambda: not app.reminders.get(reminder['id'])['pending'])
            until(lambda: not hub._reminder_busy)
            assert not app.reminders.get(reminder['id'])['pending']
            hub.pause_reminders()
            until(lambda: not app.reminders.get(reminder['id'])['enabled'])
            until(lambda: not hub._reminder_busy)
            assert not app.reminders.get(reminder['id'])['enabled']
            hub.visible.set(False)
            hub.apply_visibility()
            hub.hide()
            assert not hub.visible.get(), 'Keep the explicit desktop visibility preference'
            assert hub.window.state() == 'iconic', 'Keep a taskbar recovery surface'
            until(lambda: HubPreferences(base / 'settings.json').values['desktop_visible'] is False)
            persisted = HubPreferences(base / 'settings.json')
            assert not persisted.values['desktop_visible']
            for name in hub.pages:
                hub.show(name)
                root.update()
            memory.add_message('older-chat', 'user', 'An earlier conversation')
            memory.add_message('active-chat', 'user', 'The current conversation')
            app._live_conversation.session = SimpleNamespace(session_id='active-chat')
            hub.show_chat_history()
            until(lambda: any(row['session'] == 'older-chat' for row in (hub._session_cards or [])))
            hub.open_chat('older-chat')
            until(lambda: hub._messages == [('You', 'An earlier conversation')])
            assert hub.composer.cget('state') == 'disabled'
            hub.open_chat(None)
            until(lambda: hub._messages == [('You', 'The current conversation')])
            assert hub.composer.cget('state') == 'normal'
            def start_new_chat():
                app._live_conversation.session = SimpleNamespace(session_id='new-chat')
                return 'new-chat'
            app._live_conversation.start_new_chat = start_new_chat
            hub.new_chat()
            until(lambda: hub._view_session == 'new-chat')
            until(lambda: hub._messages == [])
            assert memory.recent(session='older-chat')
            captured = np.random.default_rng(43).integers(45,210,(100,100,3),dtype=np.uint8)
            embedding = np.random.default_rng(7).normal(size=32)
            captured_key = app.face_id.inbox.add(embedding,captured,now=1)
            hub._refresh_faces()
            until(lambda: any(row.get('pending_id') == captured_key for row in hub._face_rows))
            hub.label_captured_face(captured_key,'Papa')
            until(lambda: not app.face_id.inbox.rows())
            until(lambda: any(row['name'] == 'Papa' and not row.get('pending_id') for row in hub._face_rows))
            assert app.face_id.match_face(embedding) == 'Papa'
            assert app.face_id.list_faces()[0]['thumbnail']
            hub.close()
            until(lambda: not hub._io.alive)
            print('HUB_SMOKE_OK: six pages, Manglish/native, inline enrollment, reopen, serial send, reminders, settings, mute preserved')
        finally:
            root.destroy()


if __name__ == '__main__':
    main()
