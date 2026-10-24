"""Modern, task-focused companion UI on the existing Tk controller."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import io
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog
import webbrowser

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageOps
import cv2
import numpy as np

from .paths import DATA_DIR, MOTHER_ARTWORK_DIR
from .mother_animation import approved_fullbody
from .manglish import to_manglish
from .calendar_connection import CalendarConnection, CalendarConnectionError
from .ui_tasks import UITasks
from .character_profile import CharacterProfile
from .people_portrait import face_avatar
from .profile_backup import export_profile, preview_profile

BG = ('#f5f6f8', '#151c1a')
SURFACE = ('#ffffff', '#202a25')
INK = ('#172b26', '#e5eee8')
MUTED = ('#64736f', '#a7b6ac')
GREEN = ('#177653', '#78d9a5')
SOFT = ('#e6f2eb', '#293d32')
LINE = ('#e1e6e3', '#3b4b41')
IST = timezone(timedelta(hours=5, minutes=30))


class ModernHub:
    def __init__(self, app):
        self.app, self.preferences = app, app.hub_preferences
        ctk.set_appearance_mode(self.preferences.values.get('theme', 'light'))
        self.closed = self.pending = False
        self._last_memory_id = 0
        self._messages = []
        self._events = queue.Queue()
        self._jobs = []
        self._avatar_index = 0
        self._avatar_cache = {}
        self._enrolling = False
        self._preview = False
        self._connection_busy = False
        self._io = UITasks()
        self._reminder_rows = []
        self._history_rows = []
        self._snapshot_generation = 0
        self._ephemeral_reply = None
        self._settings_dirty = False
        self._last_avatar = None
        self._reminder_busy = False
        self._next_snapshot = 0
        self._feature_snapshot = None
        self._selected_reminder = None
        self.calendar = CalendarConnection(DATA_DIR / 'connections' / 'google-calendar')
        self.window = ctk.CTkToplevel(app.root, fg_color=BG)
        self.window.title('Setta — Home with ' + app.character_profile.name)
        scale = self.window._get_window_scaling()
        width = min(1180, int((self.window.winfo_screenwidth()-60)/scale))
        height = min(800, int((self.window.winfo_screenheight()-90)/scale))
        self.window.geometry(f'{width}x{height}+30+30')
        self.window.minsize(min(900, width), min(620, height))
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.window.grid_columnconfigure(1, weight=1)
        self.window.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self.window, width=194, corner_radius=0, fg_color=SURFACE)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.grid_propagate(False)
        self.label(self.sidebar, 'setta', 30, weight='bold').pack(anchor='w', padx=27, pady=(29, 0))
        self.label(self.sidebar, 'Your everyday companion', 11, MUTED).pack(anchor='w', padx=27, pady=(0, 33))
        self.pages, self.nav, self.page_hosts = {}, {}, {}
        self.active_page = 'Home'
        self.content = ctk.CTkFrame(self.window, corner_radius=0, fg_color=BG)
        self.content.grid(row=0, column=1, sticky='nsew', padx=25, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        for name, symbol in [('Home', '⌂'), ('Conversation', '◌'), ('Reminders', '◷'),
                             ('Camera', '◎'), ('Connections', '⇄'), ('Personality', '♡'),
                             ('Profile & Memory','◇'), ('Settings', '⚙')]:
            nav = ctk.CTkButton(self.sidebar, text=f"{symbol}    {'Chat history' if name == 'Conversation' else name}", anchor='w', height=44,
                corner_radius=10, fg_color='transparent', text_color=MUTED, hover_color=SOFT,
                font=('Segoe UI', 13), command=lambda n=name: self.show_page(n))
            nav.pack(fill='x', padx=14, pady=3)
            self.nav[name] = nav
            host = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
            host.grid(row=0, column=0, sticky='nsew')
            host.grid_rowconfigure(0, weight=1)
            host.grid_columnconfigure(0, weight=1)
            self.page_hosts[name] = host
            page = ctk.CTkFrame(host, fg_color=BG, corner_radius=0) if name == 'Conversation' else ctk.CTkScrollableFrame(host, fg_color=BG, corner_radius=0)
            page.grid(row=0, column=0, sticky='nsew')
            page.grid_columnconfigure(0, weight=1)
            self.pages[name] = page
        self.button(self.sidebar, 'Back to desktop', self.hide, secondary=True).pack(side='bottom', fill='x', padx=18, pady=(6, 20))
        self.button(self.sidebar, 'Quit Setta', app._exit_app, secondary=True).pack(side='bottom', fill='x', padx=18)
        self.notice = tk.StringVar(value='')
        self.notice_label = self.label(self.window, '', 11, MUTED, textvariable=self.notice)
        self.notice_label.grid(row=1, column=0, columnspan=2, sticky='ew', padx=20, pady=4)
        self.visible = tk.BooleanVar(value=self.preferences.values['desktop_visible'])
        self.walking = tk.BooleanVar(value=self.preferences.values['walking'])
        self.status = tk.StringVar(value='Ready when you are')
        self.next_reminder = tk.StringVar(value='No reminder scheduled')
        self.reminder_status = tk.StringVar(value='')
        self.camera_status = tk.StringVar(value='')
        self._home()
        self._conversation()
        self._reminders()
        self._camera()
        self._connections()
        self._settings()
        self.show_page('Home')
        self._tick()
        self._animate_avatar()
        self._drain_io()

    def label(self, parent, text, size=13, color=INK, weight='normal', **kwargs):
        anchor = kwargs.pop('anchor', 'w')
        justify = kwargs.pop('justify', 'left')
        return ctk.CTkLabel(parent, text=text, text_color=color, font=('Segoe UI', size, weight),
                            anchor=anchor, justify=justify, **kwargs)

    def button(self, parent, text, command, secondary=False, **kwargs):
        height = kwargs.pop('height', 40)
        return ctk.CTkButton(parent, text=text, command=command, height=height, corner_radius=9,
            fg_color=SOFT if secondary else ('#177653', '#21744f'), text_color=GREEN if secondary else '#ffffff',
            hover_color=('#d6e9dd', '#36503f') if secondary else ('#0f5f42', '#286f4e'), font=('Segoe UI', 12, 'bold'),
            border_width=0, **kwargs)

    def card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=16, border_width=1,
                            border_color=LINE, **kwargs)

    def header(self, page, title, subtitle):
        heading = self.label(page, title, 28, weight='bold')
        heading.pack(anchor='w', pady=(5, 2))
        self.label(page, subtitle, 12, MUTED, wraplength=720).pack(anchor='w', pady=(0, 22))
        return heading

    def _home(self):
        page = self.pages['Home']
        self.header(page, 'A little company. A little care.', 'Your day, with ' + self.app.character_profile.name + ' by your side.')
        layout = ctk.CTkFrame(page, fg_color='transparent')
        layout.pack(fill='x')
        layout.grid_columnconfigure(0, weight=3)
        layout.grid_columnconfigure(1, weight=2)
        hero = self.card(layout)
        hero.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        self.home_identity = self.label(hero, '●  ' + self.app.character_profile.name + ' is here', 13, GREEN, 'bold')
        self.home_identity.pack(anchor='w', padx=22, pady=(18, 0))
        self.avatar = ctk.CTkLabel(hero, text='', height=360)
        self.avatar.pack(fill='x', padx=12)
        self._rest_image = approved_fullbody(MOTHER_ARTWORK_DIR / 'mother-likeness-v6.png', (270, 365))
        self._rest_avatar = ctk.CTkImage(self._rest_image, size=(270, 365))
        self.avatar.configure(image=self._rest_avatar)
        self.label(hero, '', 12, MUTED, textvariable=self.status).pack(padx=22, pady=(0, 12))
        row = ctk.CTkFrame(hero, fg_color='transparent')
        row.pack(fill='x', padx=20, pady=(0, 20))
        self.button(row, 'Let’s talk', lambda: self.show_page('Conversation')).pack(side='left', fill='x', expand=True)
        self.button(row, 'Wave', lambda: self.preview_expression('wave'), True, width=80).pack(side='left', padx=(8, 0))
        right = ctk.CTkFrame(layout, fg_color='transparent')
        right.grid(row=0, column=1, sticky='nsew')
        day = self.card(right)
        day.pack(fill='x', pady=(0, 12))
        self.label(day, datetime.now(IST).strftime('%A, %d %B'), 12, MUTED).pack(anchor='w', padx=20, pady=(18, 2))
        self.label(day, 'Your next little nudge', 17, weight='bold').pack(anchor='w', padx=20)
        self.label(day, '', 13, MUTED, textvariable=self.next_reminder, wraplength=245).pack(anchor='w', padx=20, pady=14)
        self.button(day, 'Manage reminders', lambda: self.show_page('Reminders'), True).pack(fill='x', padx=20, pady=(0, 18))
        face_card = self.card(right)
        face_card.pack(fill='x', pady=(0, 12))
        with Image.open(MOTHER_ARTWORK_DIR / 'mother-likeness-v6.png') as original:
            portrait = original.convert('RGBA').crop((135, 28, 850, 780))
        self._portrait = ctk.CTkImage(portrait, size=(104, 110))
        ctk.CTkLabel(face_card, text='', image=self._portrait).pack(side='left', padx=(12, 8), pady=12)
        self.label(face_card, 'The familiar face\nyou chose.', 13, wraplength=120).pack(side='left', padx=(0, 8))
        connect = self.card(right)
        connect.pack(fill='x')
        self.label(connect, 'Make room for your day', 16, weight='bold', wraplength=240).pack(anchor='w', padx=20, pady=(16, 6))
        self.label(connect, 'Connect your calendar and see\nwhat’s coming up.', 12, MUTED).pack(anchor='w', padx=20)
        self.button(connect, 'Explore connections', lambda: self.show_page('Connections'), True).pack(fill='x', padx=20, pady=16)
        quick = ctk.CTkFrame(page, fg_color='transparent')
        quick.pack(fill='x', pady=16)
        self.button(quick, 'Walk on desktop', self.walk, True).pack(side='left', padx=(0, 8))
        self.button(quick, 'Stay still', self.stay, True).pack(side='left', padx=(0, 8))
        self.button(quick, 'Smile', lambda: self.preview_expression('smile'), True, width=90).pack(side='left')

    def _conversation(self):
        page = self.pages['Conversation']
        self.conversation_title = self.header(page, 'Chat history', 'Separate conversations, saved on this laptop.')
        navigation = ctk.CTkFrame(page, fg_color='transparent')
        navigation.pack(fill='x', pady=(0, 12))
        self.button(navigation, 'All chats', self.show_chat_history, True, width=110).pack(side='left')
        self.button(navigation, 'New chat', self.new_chat, width=110).pack(side='right')
        self.button(navigation, 'Current chat', lambda: self.open_chat(None), True, width=110).pack(side='right', padx=8)
        self.chat_cards = ctk.CTkScrollableFrame(page, fg_color='transparent')
        self.chat_cards.pack(fill='both', expand=True)
        self.chat_detail = ctk.CTkFrame(page, fg_color='transparent')
        self._session_cards = None
        self._view_session = None
        self._archive_view = False
        self.transcript = ctk.CTkTextbox(self.chat_detail, fg_color=SURFACE, text_color=INK, corner_radius=14,
            border_width=1, border_color=LINE, font=('Segoe UI', 14), wrap='word')
        self.transcript.pack(fill='both', expand=True)
        self.transcript.configure(state='disabled')
        self.chat_status = tk.StringVar(value='Type a message. Your microphone stays off.')
        self.label(self.chat_detail, '', 11, MUTED, textvariable=self.chat_status, wraplength=720).pack(anchor='w', pady=(9, 7))
        composer = ctk.CTkFrame(self.chat_detail, fg_color='transparent')
        composer.pack(fill='x')
        self.composer = ctk.CTkEntry(composer, placeholder_text='Tell Amma something…', height=46,
            fg_color=SURFACE, border_color=LINE, corner_radius=10, font=('Segoe UI', 14), text_color=INK)
        self.composer.pack(side='left', fill='x', expand=True)
        self.composer.bind('<Return>', lambda event: self.send())
        self.send_button = self.button(composer, 'Send', self.send, width=85)
        self.send_button.pack(side='left', padx=(10, 0))
        tools = ctk.CTkFrame(self.chat_detail, fg_color='transparent')
        tools.pack(fill='x', pady=12)
        self.button(tools, 'Open hands-free', self.app._open_handsfree, True).pack(side='left')
        self.button(tools, 'Stop desktop voice', self.mute, True).pack(side='left', padx=8)
        self.button(tools, 'Copy last reply', self.copy_last_reply, True, width=125).pack(side='right')
        suggestions = ctk.CTkFrame(self.chat_detail, fg_color='transparent')
        suggestions.pack(fill='x', pady=(0, 8))
        for text in ('Help me plan my day', 'What did we discuss?', 'I need encouragement'):
            self.button(suggestions, text, lambda t=text: self.prefill_message(t), True, width=170).pack(side='left', padx=(0, 6))
        self._refresh_history()

    def show_chat_history(self):
        self.chat_detail.pack_forget()
        self.chat_cards.pack(fill='both', expand=True)
        self._request_snapshot()

    def open_chat(self, session=None):
        if self.pending:
            self.notice.set('Wait for the current reply before opening another chat.')
            return
        live = self.app._live_conversation
        current = getattr(getattr(live, 'session', None), 'session_id', None)
        self._view_session = session or current
        self._ephemeral_reply = None
        self._archive_view = bool(session and session != current)
        self.chat_cards.pack_forget()
        self.chat_detail.pack(fill='both', expand=True)
        self.composer.configure(state='disabled' if self._archive_view else 'normal')
        self.send_button.configure(state='disabled' if self._archive_view or self.pending else 'normal')
        self.chat_status.set('Saved conversation. Choose New chat or Current chat to talk.' if self._archive_view else 'Ready for your next thought.')
        self._snapshot_generation += 1
        self._history_rows = None
        self._request_snapshot()

    def new_chat(self):
        live = self.app._live_conversation
        if self.pending or getattr(self, '_new_chat_pending', False) or getattr(self.app, '_external_handsfree_active', False) or bool(self.app.voice_agent and self.app.voice_agent.active):
            self.notice.set('Finish the current reply or stop hands-free before starting a new chat.')
            return
        if not live or not hasattr(live, 'start_new_chat'):
            self.notice.set('Conversation is not configured yet.')
            return
        def complete(session, error):
            self._new_chat_pending = False
            self.send_button.configure(state='normal')
            if error:
                self.notice.set('Could not start a new chat. Please try again.')
                return
            self._ephemeral_reply = None
            self._messages = []
            self.open_chat(session)
        if self._io.submit('new_chat', live.start_new_chat, complete):
            self._new_chat_pending = True
            self.send_button.configure(state='disabled')

    def _render_chat_cards(self, sessions):
        if sessions == self._session_cards:
            return
        self._session_cards = sessions
        for widget in self.chat_cards.winfo_children():
            widget.destroy()
        if not sessions:
            self.label(self.chat_cards, 'Your conversations will appear here. Choose New chat to begin.', 15, MUTED, wraplength=550).pack(anchor='w', pady=25)
        for session in sessions:
            card = ctk.CTkFrame(self.chat_cards, fg_color=SURFACE, corner_radius=14)
            card.pack(fill='x', pady=(0, 12))
            self.button(card, self.display(session['title'] or 'Conversation')[:70], lambda key=session['session']: self.open_chat(key), True).pack(fill='x', padx=16, pady=(16, 8))
            try:
                start = datetime.fromisoformat(session['started_at']).astimezone(IST).strftime('%d %b %Y · %I:%M %p')
                end = datetime.fromisoformat(session['ended_at']).astimezone(IST).strftime('%I:%M %p')
            except (ValueError, TypeError):
                start, end = session['started_at'], session['ended_at']
            self.label(card, f"{start} — {end} · {session['messages']} messages", 12, MUTED).pack(anchor='w', padx=16, pady=(0, 16))

    def prefill_message(self, text):
        if self.pending:
            return
        self.composer.delete(0, 'end')
        self.composer.insert(0, text)
        self.composer.focus_set()

    def copy_last_reply(self):
        reply = next((text for speaker, text in reversed(self._messages) if speaker != 'You'), None)
        if reply:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.display(reply))
            self.chat_status.set('Last reply copied.')
        else:
            self.chat_status.set('There is no reply to copy yet.')

    def display(self, text):
        return to_manglish(str(text)) if self.preferences.values['display_script'] == 'manglish' else str(text)

    def add_message(self, speaker, text):
        self._messages.append((speaker, str(text)))
        self._messages = self._messages[-150:]
        self._render_messages()

    def _render_messages(self):
        self.transcript.configure(state='normal')
        self.transcript.delete('1.0', 'end')
        if not self._messages:
            self.transcript.insert('end', 'Make yourself comfortable. What’s on your mind?\n')
        dark = ctk.get_appearance_mode() == 'Dark'
        self.transcript.tag_config('person', foreground='#78d9a5' if dark else '#177653', spacing1=12, spacing3=6, lmargin1=20, lmargin2=20)
        self.transcript.tag_config('you', foreground='#b8c7bf' if dark else '#64736f', spacing1=12, spacing3=6, lmargin1=45, lmargin2=45)
        self.transcript.tag_config('reply', lmargin1=20, lmargin2=20, rmargin=30, spacing3=16)
        self.transcript.tag_config('message', lmargin1=45, lmargin2=45, rmargin=20, spacing3=16)
        for speaker, text in self._messages[-150:]:
            own = speaker == 'You'
            self.transcript.insert('end', speaker + '\n', 'you' if own else 'person')
            self.transcript.insert('end', self.display(text) + '\n\n', 'message' if own else 'reply')
        self.transcript.configure(state='disabled')
        self.transcript.see('end')

    def _refresh_history(self):
        self._request_snapshot()

    def _request_snapshot(self):
        generation = self._snapshot_generation
        live, reminders = self.app._live_conversation, self.app.reminders
        selected = self._view_session or getattr(getattr(live, 'session', None), 'session_id', None)
        def read():
            return generation, live.memory.recent(limit=150, session=selected) if live else [], reminders.list(), reminders.quiet_hours(), reminders.history(limit=40), live.memory.sessions() if live else []
        self._io.submit('snapshot', read, self._apply_snapshot)

    def _apply_snapshot(self, value, error):
        if error:
            self.notice.set('Local storage is busy. You can keep using the app while it retries.')
            return
        generation, history, reminders, quiet, reminder_history, sessions = value
        self._render_chat_cards(sessions)
        self._refresh_features(reminders, quiet, reminder_history)
        self._reminder_rows = reminders
        self._refresh_reminders()
        if self.active_page == 'Camera':
            self._refresh_faces()
        if generation != self._snapshot_generation:
            self._request_snapshot()
            return
        if not self.pending and history != self._history_rows:
            self._history_rows = history
            self._messages = [('You' if row['role'] == 'user' else self.app.character_profile.name,
                                row['text']) for row in history]
            if self._ephemeral_reply:
                if self._messages and self._messages[-1] == self._ephemeral_reply:
                    self._ephemeral_reply = None
                else:
                    self._messages.append(self._ephemeral_reply)
            self._render_messages()

    def _drain_io(self):
        if self.closed:
            return
        self._io.drain()
        self._io_job = self.window.after(30, self._drain_io)

    def send(self):
        prompt = self.composer.get().strip()
        if not prompt or self.pending or self._archive_view or getattr(self, '_new_chat_pending', False):
            return
        if 'enroll' in prompt.casefold() and 'face' in prompt.casefold():
            self.composer.delete(0, 'end')
            self.show_page('Camera')
            self.enroll_name.focus_set()
            return
        agent = self.app.voice_agent
        if getattr(self.app, '_external_handsfree_active', False) or bool(agent and agent.active):
            self.chat_status.set('Stop the active microphone session before sending a typed message.')
            return
        if not self.app._live_conversation:
            self.chat_status.set('Conversation isn’t configured. Your message has not been sent.')
            return
        self.pending = True
        self._ephemeral_reply = None
        self.send_button.configure(state='disabled', text='Sending…')
        self.chat_status.set('Amma is thinking…')
        self.composer.delete(0, 'end')
        self.add_message('You', prompt)
        self.app._submit_hub_chat(prompt)

    def receive_reply(self, reply):
        if self.pending:
            self.add_message(self.app.character_profile.name, reply)
            self._ephemeral_reply = (self.app.character_profile.name, str(reply))
        self.pending = False
        self._snapshot_generation += 1
        self._request_snapshot()
        self.send_button.configure(state='normal', text='Send')
        self.chat_status.set('Ready for your next thought.')

    def _reminders(self):
        page = self.pages['Reminders']
        self.header(page, 'Small habits, gentle nudges', 'Set a rhythm that works for you. You can always snooze or skip.')
        self._extra_reminders(page)
        self.button(page, 'Water quick setup', self.toggle_water_setup, True).pack(anchor='w', pady=12)
        card = self.card(page)
        self._water_setup = card
        card.pack(fill='x')
        self.label(card, 'Water break', 21, weight='bold').pack(anchor='w', padx=24, pady=(22, 3))
        self.label(card, 'A quick check-in to keep a glass nearby.', 12, MUTED).pack(anchor='w', padx=24)
        self.label(card, 'How often should Amma check in?', 13, weight='bold').pack(anchor='w', padx=24, pady=(25, 10))
        self.interval = tk.StringVar(value='60')
        preset = ctk.CTkFrame(card, fg_color='transparent')
        preset.pack(anchor='w', padx=24)
        for minutes in (30, 45, 60, 90):
            self.button(preset, f'{minutes} min', lambda m=minutes: self.interval.set(str(m)), True, width=92).pack(side='left', padx=(0, 8))
        custom = ctk.CTkFrame(card, fg_color='transparent')
        custom.pack(fill='x', padx=24, pady=16)
        self.interval_entry = ctk.CTkEntry(custom, textvariable=self.interval, width=80, height=40, border_color=LINE)
        self.interval_entry.pack(side='left')
        arrows = ctk.CTkFrame(custom, fg_color='transparent')
        arrows.pack(side='left', padx=(5, 0))
        self.button(arrows, '＋', lambda: self.adjust_interval(1), True, width=38).pack(side='left')
        self.button(arrows, '−', lambda: self.adjust_interval(-1), True, width=38).pack(side='left', padx=(4, 0))
        self.interval_entry.bind('<MouseWheel>', self.wheel_interval)
        self.interval_entry.bind('<Up>', lambda event: self.adjust_interval(1))
        self.interval_entry.bind('<Down>', lambda event: self.adjust_interval(-1))
        self.label(custom, 'minutes', 12, MUTED).pack(side='left', padx=10)
        self.button(custom, 'Save water reminder', self.start_water).pack(side='left', padx=12)
        self.label(card, '', 15, textvariable=self.reminder_status, wraplength=650).pack(anchor='w', padx=24, pady=(12, 16))
        controls = ctk.CTkFrame(card, fg_color='transparent')
        controls.pack(anchor='w', padx=24, pady=(0, 20))
        self.reminder_actions = []
        for text, action in [('I drank water', 'done'), ('Snooze 5 min', 'snooze'), ('Skip', 'skip')]:
            button = self.button(controls, text, lambda a=action: self.ack(a), action != 'done', width=120)
            button.pack(side='left', padx=(0, 8))
            self.reminder_actions.append(button)
        self.reminder_toggle = self.button(card, 'Pause reminders', self.pause_reminders, True)
        self.reminder_toggle.pack(anchor='w', pady=16)
        self.label(page, 'You choose how to confirm. No camera proof is required.\nReminders run while Setta is open, with one check-in at a time.',
                   12, MUTED, wraplength=700).pack(anchor='w', pady=8)
        card.pack_forget()

    def toggle_water_setup(self):
        if self._water_setup.winfo_manager():
            self._water_setup.pack_forget()
        else:
            self._water_setup.pack(fill='x', pady=12)

    def _extra_reminders(self, page):
        card = self.card(page)
        card.pack(fill='x', pady=16)
        self.label(card, 'Your reminders', 21, weight='bold').pack(anchor='w', padx=24, pady=(20, 6))
        self.label(card, 'Editing restarts the interval. Times use India Standard Time.', 12, MUTED).pack(anchor='w', padx=24)
        self.habit_choice = ctk.CTkOptionMenu(card, values=['New reminder'], command=self.select_habit, fg_color=SOFT, text_color=INK)
        self.habit_choice.pack(fill='x', padx=24, pady=12)
        self.habit_title = ctk.CTkEntry(card, placeholder_text='Reminder name, e.g. Stretch', height=40)
        self.habit_title.pack(fill='x', padx=24)
        row = ctk.CTkFrame(card, fg_color='transparent')
        row.pack(fill='x', padx=24, pady=12)
        self.habit_minutes = ctk.CTkEntry(row, width=80, height=40)
        self.habit_minutes.insert(0, '60')
        self.habit_minutes.pack(side='left')
        self.label(row, 'minutes', 12, MUTED).pack(side='left', padx=8)
        self.button(row, 'Save habit', self.save_habit).pack(side='left', padx=8)
        self.button(row, 'New', lambda: self.select_habit('New reminder'), True, width=65).pack(side='left')
        self.habit_state = tk.StringVar(value='Add a habit to begin.')
        self.label(card, '', 13, textvariable=self.habit_state, wraplength=650).pack(anchor='w', padx=24, pady=8)
        actions = ctk.CTkFrame(card, fg_color='transparent')
        actions.pack(fill='x', padx=24, pady=(0, 20))
        for title, action in [('Done', 'done'), ('Snooze', 'snooze'), ('Skip', 'skip'), ('Pause / resume', 'toggle'), ('Archive', 'archive')]:
            self.button(actions, title, lambda a=action: self.habit_action(a), True, width=100).pack(side='left', padx=(0, 6))
        quiet = self.card(page)
        quiet.pack(fill='x', pady=(0, 16))
        self.quiet_enabled = tk.BooleanVar(value=False)
        ctk.CTkSwitch(quiet, text='Quiet hours for Amma reminders', variable=self.quiet_enabled, text_color=INK, progress_color=GREEN).pack(anchor='w', padx=24, pady=(20, 12))
        times = ctk.CTkFrame(quiet, fg_color='transparent')
        times.pack(fill='x', padx=24, pady=(0, 12))
        self.quiet_start = ctk.CTkEntry(times, width=85)
        self.quiet_end = ctk.CTkEntry(times, width=85)
        self.quiet_start.insert(0, '22:00')
        self.quiet_end.insert(0, '08:00')
        self.quiet_start.pack(side='left')
        self.label(times, 'to', 12, MUTED).pack(side='left', padx=12)
        self.quiet_end.pack(side='left')
        self.button(times, 'Save quiet hours', self.save_quiet, True).pack(side='left', padx=12)
        self.label(quiet, '24-hour time · Asia/Kolkata. Missed check-ins restart after quiet hours; no catch-up burst.', 12, MUTED, wraplength=650).pack(anchor='w', padx=24, pady=(0, 20))
        self.label(page, 'Recent reminder activity', 20, weight='bold').pack(anchor='w', pady=(8, 6))
        self.label(page, 'Done means you confirmed it. Camera proof is not collected.', 12, MUTED).pack(anchor='w')
        self.reminder_history = ctk.CTkTextbox(page, height=200, fg_color=SURFACE, text_color=INK)
        self.reminder_history.pack(fill='x', pady=12)
        self.reminder_history.configure(state='disabled')

    def _refresh_features(self, rows, quiet, history):
        snapshot = (rows, quiet, history)
        if snapshot == self._feature_snapshot:
            return
        first = self._feature_snapshot is None
        self._feature_snapshot = snapshot
        self._habit_options = {'New reminder': None, **{f"{r['id']} · {r['title']}": r['id'] for r in rows}}
        self.habit_choice.configure(values=list(self._habit_options))
        selected = next((r for r in rows if r['id'] == self._selected_reminder), None)
        if selected:
            self.habit_choice.set(f"{selected['id']} · {selected['title']}")
            status = ('Completed' if selected.get('one_shot') and selected.get('last_ack') in ('done', 'skip') else 'Paused') if not selected['enabled'] else 'Ready for your check-in' if selected['pending'] else 'Next: ' + datetime.fromtimestamp(selected['next_due'], IST).strftime('%d %b %I:%M %p')
            self.habit_state.set(status)
        elif self._selected_reminder is not None:
            self.select_habit('New reminder')
        if first:
            self.quiet_enabled.set(quiet['enabled'])
            for entry, value in [(self.quiet_start, quiet['start']), (self.quiet_end, quiet['end'])]:
                entry.delete(0, 'end')
                entry.insert(0, value)
        labels = {'done': 'Confirmed by you', 'due': 'Check-in shown', 'quiet_deferred': 'Deferred for quiet hours'}
        text = '\n'.join(datetime.fromtimestamp(h['at'], IST).strftime('%d %b %I:%M %p') + ' · ' + h['title'] + ' · ' + labels.get(h['action'], h['action'].replace('_', ' ').title()) for h in history) or 'Your reminder activity will appear here.'
        self.reminder_history.configure(state='normal')
        self.reminder_history.delete('1.0', 'end')
        self.reminder_history.insert('end', text)
        self.reminder_history.configure(state='disabled')

    def select_habit(self, value):
        self._selected_reminder = getattr(self, '_habit_options', {}).get(value)
        row = next((r for r in self._reminder_rows if r['id'] == self._selected_reminder), None)
        self.habit_choice.set(value)
        for entry, text in [(self.habit_title, row['title'] if row else ''), (self.habit_minutes, str(row['interval_minutes']) if row else '60')]:
            entry.delete(0, 'end')
            entry.insert(0, text)
        self.habit_state.set('Editing this reminder.' if row else 'Add a habit to begin.')

    def save_habit(self):
        title = self.habit_title.get().strip()
        try:
            minutes = float(self.habit_minutes.get())
            if not title or not 1 <= minutes <= 1440:
                raise ValueError()
        except ValueError:
            self.notice.set('Enter a name and an interval from 1 to 1440 minutes.')
            return
        reminder_id = self._selected_reminder
        def work():
            return self.app.reminders.update(reminder_id, title, minutes) if reminder_id else self.app.reminders.create(title, minutes)
        self._reminder_action(work, 'Habit saved. Choose it from Your reminders to manage it.')

    def habit_action(self, action):
        row = next((r for r in self._reminder_rows if r['id'] == self._selected_reminder), None)
        if not row:
            self.notice.set('Choose a saved reminder first.')
            return
        if action in {'done', 'skip', 'snooze'} and not (row['enabled'] and row['pending']):
            self.notice.set('There is no pending check-in for this reminder.')
            return
        def work():
            if action == 'archive':
                return self.app.reminders.archive(row['id'])
            if action == 'toggle':
                return self.app.reminders.set_enabled(row['id'], not bool(row['enabled']))
            return self.app.reminders.ack(row['id'], action)
        self._reminder_action(work, 'Reminder updated.')

    def save_quiet(self):
        enabled, start, end = self.quiet_enabled.get(), self.quiet_start.get(), self.quiet_end.get()
        def work():
            return self.app.reminders.set_quiet_hours(enabled, start, end)
        self._reminder_action(work, 'Quiet hours saved for Amma reminders (India Standard Time).')

    def _water_reminder(self):
        return next((row for row in reversed(self._reminder_rows) if row['kind'] == 'water'), None)

    def adjust_interval(self, step):
        try:
            value = int(self.interval.get())
        except ValueError:
            value = 60
        self.interval.set(str(max(1, min(1440, value + step))))
        return 'break'

    def wheel_interval(self, event):
        if event.delta:
            self.adjust_interval(1 if event.delta > 0 else -1)
        return 'break'

    def start_water(self):
        try:
            value = int(self.interval.get())
            if not 1 <= value <= 1440:
                raise ValueError()
        except ValueError:
            self.notice.set('Choose a reminder interval from 1 to 1440 minutes.')
            return
        def save():
            for row in self.app.reminders.list():
                if row['enabled'] and row['kind'] == 'water':
                    self.app.reminders.set_enabled(row['id'], False)
            return self.app.reminders.create_water(value)
        self._reminder_action(save, 'Water reminder saved. You can change it at any time.')

    def ack(self, action):
        row = self._water_reminder()
        if row:
            self._reminder_action(lambda: self.app.reminders.ack(row['id'], action),
                {'done': 'Noted. Your next check-in is scheduled.', 'skip': 'Skipped this time.', 'snooze': 'We’ll check back in five minutes.'}[action])

    def pause_reminders(self):
        row = self._water_reminder()
        if row:
            self._reminder_action(lambda: self.app.reminders.set_enabled(row['id'], not bool(row['enabled'])),
                                  'Water reminder updated.')

    def _reminder_action(self, work, message):
        def complete(value, error):
            self._reminder_busy = False
            self.notice.set(str(error) if isinstance(error, ValueError) else 'Could not update the reminder. Please try again.' if error else message)
            self._request_snapshot()
        if self._io.submit('reminder_write', work, complete):
            self._reminder_busy = True
            self.notice.set('Saving your reminder…')
            self._refresh_reminders()
        else:
            self.notice.set('A reminder update is in progress. Please wait a moment.')

    def poll_reminders(self):
        def complete(rows, error):
            if error:
                return
            if rows:
                titles = ', '.join(row['title'] for row in rows[:3])
                extra = f' and {len(rows)-3} more' if len(rows) > 3 else ''
                self.app.show_speech_bubble(titles + extra + '. Open Reminders to check in.', duration=10)
            if rows:
                self._request_snapshot()
        self._io.submit('reminder_due', self.app.reminders.due, complete)

    def _refresh_reminders(self):
        row = self._water_reminder()
        if not row:
            text = 'Choose your first water reminder.'
        elif not row['enabled']:
            text = 'Water reminders are paused.'
        elif row['pending']:
            text = 'Did you drink some water?'
        else:
            when = datetime.fromtimestamp(row['next_due'], IST).strftime('%I:%M %p').lstrip('0')
            text = f"Next check-in at {when} · every {row['interval_minutes']:g} minutes"
        self._set_text(self.reminder_status, text)
        active = [item for item in self._reminder_rows if item['enabled']]
        if active:
            pending = [item for item in active if item['pending']]
            if pending:
                summary = f"{len(pending)} check-in(s) waiting in Reminders"
            else:
                upcoming = min(active, key=lambda item: item['next_due'])
                summary = upcoming['title'] + ' · ' + datetime.fromtimestamp(upcoming['next_due'], IST).strftime('%I:%M %p')
        else:
            summary = 'No active reminders. Add a habit in Reminders.'
        self._set_text(self.next_reminder, summary)
        for button in self.reminder_actions:
            state = 'normal' if not self._reminder_busy and row and row['enabled'] and row['pending'] else 'disabled'
            if button.cget('state') != state:
                button.configure(state=state)
        text = 'Resume reminders' if row and not row['enabled'] else 'Pause reminders'
        state = 'normal' if row and not self._reminder_busy else 'disabled'
        if self.reminder_toggle.cget('text') != text or self.reminder_toggle.cget('state') != state:
            self.reminder_toggle.configure(text=text, state=state)

    def _camera(self):
        page = self.pages['Camera']
        self.header(page, 'People & camera',
            'Face references stay on this laptop. Study checks may send one camera still and the active YouTube title to Groq; Setta does not save the still.')
        columns = ctk.CTkFrame(page, fg_color='transparent')
        columns.pack(fill='x')
        columns.grid_columnconfigure((0, 1), weight=1, uniform='camera')
        self.camera_columns = columns

        camera = self.card(columns)
        self.camera_card = camera
        camera.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        camera_heading = ctk.CTkFrame(camera, fg_color='transparent')
        camera_heading.pack(fill='x', padx=18, pady=(16, 8))
        self.label(camera_heading, 'Live camera', 18, weight='bold').pack(side='left')
        self.camera_state_label = self.label(camera_heading, 'Camera off', 11, MUTED)
        self.camera_state_label.pack(side='right')
        self.camera_preview = ctk.CTkLabel(camera, text='Camera is off\nNothing is being captured.',
            height=236, text_color=MUTED, fg_color=SOFT, corner_radius=12,
            font=('Segoe UI', 14))
        self.camera_preview.pack(fill='x', padx=16, pady=(0, 12))
        camera_controls = ctk.CTkFrame(camera, fg_color='transparent')
        camera_controls.pack(fill='x', padx=16, pady=(0, 14))
        self.camera_toggle = self.button(camera_controls, 'Turn camera on', self.toggle_preview)
        self.camera_toggle.pack(side='left')
        self.label(camera_controls, '', 11, MUTED, textvariable=self.camera_status,
                   wraplength=180).pack(side='left', padx=(12, 0))

        self.drop_zone = self.card(columns)
        self.drop_zone.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        self.label(self.drop_zone, 'Add a person', 18, weight='bold').pack(anchor='w', padx=18, pady=(16, 4))
        self.label(self.drop_zone, 'Use a live camera sample or one clear photo.', 12, MUTED).pack(anchor='w', padx=18, pady=(0, 10))
        self.enroll_name = ctk.CTkEntry(self.drop_zone, placeholder_text='Name this person', height=40, border_color=LINE)
        self.enroll_name.pack(fill='x', padx=18, pady=(0, 10))
        self.photo_drop_target = ctk.CTkFrame(self.drop_zone, fg_color=BG, corner_radius=12,
            border_width=1, border_color=LINE, height=95)
        self.photo_drop_target.pack(fill='x', padx=18, pady=(0, 10))
        self.photo_drop_target.pack_propagate(False)
        self.drop_hint = self.label(self.photo_drop_target, 'Drop a photo here · one clear face works best', 12, MUTED)
        self.drop_hint.pack(expand=True, pady=(12, 2))
        self.photo_enroll_button = self.button(self.photo_drop_target, 'Browse photos', self.enroll_photo, True, height=34)
        self.photo_enroll_button.pack(pady=(0, 10))
        self.enroll_button = self.button(self.drop_zone, 'Save face from camera', self.enroll_face)
        self.enroll_button.pack(anchor='w', padx=18, pady=(0, 8))
        self.enrollment_status = tk.StringVar(value='Add a name, then choose a photo or turn on the camera.')
        self.label(self.drop_zone, '', 11, MUTED, textvariable=self.enrollment_status,
                   wraplength=360).pack(anchor='w', padx=18, pady=(0, 6))
        self.enrollment_progress = ctk.CTkProgressBar(self.drop_zone, mode='indeterminate', progress_color=GREEN)
        self.enrollment_progress.pack(fill='x', padx=18, pady=(0, 14))
        self.enrollment_progress.set(0)

        self._drop_ready = False
        try:
            from tkinterdnd2 import TkinterDnD, DND_FILES
            TkinterDnD._require(self.app.root)
            for widget in (self.drop_zone, self.photo_drop_target, self.drop_hint, self.photo_enroll_button):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind('<<Drop>>', self.drop_photo)
            self._drop_ready = True
        except (ImportError, RuntimeError, tk.TclError):
            self.drop_hint.configure(text='Browse for a JPG, PNG or WebP photo')

        saved_faces = self.card(page)
        saved_faces.pack(fill='x', pady=(16, 10))
        people_heading = ctk.CTkFrame(saved_faces, fg_color='transparent')
        people_heading.pack(fill='x', padx=18, pady=(14, 3))
        self.label(people_heading, 'People Setta knows', 20, weight='bold').pack(side='left')
        self._people_edit = False
        self.people_edit_button = self.button(people_heading, 'Edit people', self.toggle_people_edit, True, width=105, height=34)
        self.people_edit_button.pack(side='right')
        self.label(saved_faces, 'Select a face to add another sample. New people stay unnamed until you confirm who they are.',
                   11, MUTED, wraplength=690).pack(anchor='w', padx=18, pady=(0, 5))
        self.face_review_banner = ctk.CTkFrame(saved_faces, fg_color=SOFT, corner_radius=10)
        self.face_gallery = ctk.CTkFrame(saved_faces, fg_color='transparent')
        self.face_gallery.pack(fill='x', padx=18, pady=(8, 14), anchor='w')

        recognition = self.card(page)
        recognition.pack(fill='x', pady=(0, 12))
        self.label(recognition, 'Recognition settings', 16, weight='bold').pack(anchor='w', padx=18, pady=(14, 4))
        self.discover_people = tk.BooleanVar(value=self.preferences.values.get('face_discovery', True))
        ctk.CTkSwitch(recognition, text='Find new people while the camera is on', variable=self.discover_people,
            command=self.toggle_discovery, text_color=INK, progress_color=GREEN).pack(anchor='w', padx=18, pady=(4, 0))
        self.label(recognition, 'New face photos are kept on this laptop until you name or discard them. Up to 12 can wait for review.',
                   11, MUTED, wraplength=680).pack(anchor='w', padx=48, pady=(0, 8))
        self.collect_faces = tk.BooleanVar(value=self.preferences.values.get('face_candidates', False))
        if getattr(self.app, 'face_id', None):
            self.app.face_id.capture_candidates = False
        ctk.CTkSwitch(recognition, text='Suggest repeat appearances for review', variable=self.collect_faces,
            command=self.toggle_face_candidates, text_color=INK, progress_color=GREEN).pack(anchor='w', padx=18, pady=(0, 0))
        self.label(recognition, 'Suggestions need your approval before they are added to a person.', 11, MUTED,
                   wraplength=680).pack(anchor='w', padx=48, pady=(0, 14))

        self._face_rows = None
        self._face_images = []
        self._pending_face_entries = {}
        self._camera_columns_wide = None
        self.window.bind('<Configure>', self._layout_camera_panels, add='+')
        self.content.bind('<Configure>', self._layout_camera_panels, add='+')
        self._layout_camera_panels()
        self._refresh_faces()

    def _layout_camera_panels(self, event=None):
        if event is not None and event.widget not in (self.window, self.content):
            return
        wide = self.content.winfo_width() >= 820
        if wide == self._camera_columns_wide:
            return
        self._camera_columns_wide = wide
        if wide:
            self.camera_card.grid(row=0, column=0, columnspan=1, sticky='nsew', padx=(0, 8), pady=0)
            self.drop_zone.grid(row=0, column=1, columnspan=1, sticky='nsew', padx=(8, 0), pady=0)
        else:
            self.camera_card.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=0, pady=(0, 10))
            self.drop_zone.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)

    def _refresh_faces(self):
        face_id = getattr(self.app, 'face_id', None)
        if face_id is None:
            return
        def complete(rows, error):
            if error:
                self.enrollment_status.set('Could not load saved faces. Try reopening Camera.')
                return
            if getattr(self, '_faces_refresh_requested', False):
                self._faces_refresh_requested = False
                self._refresh_faces()
            if rows == self._face_rows:
                return
            self._face_rows = rows
            for child in self.face_gallery.winfo_children():
                child.destroy()
            self._face_images = []
            self._pending_face_entries = {}
            pending_rows = [row for row in rows if row.get('pending_id')]
            if pending_rows:
                for child in self.face_review_banner.winfo_children():
                    child.destroy()
                count = len(pending_rows)
                self.face_review_banner.pack(fill='x', padx=18, pady=(8, 0), before=self.face_gallery)
                self.label(self.face_review_banner, f"{count} new face{'s' if count != 1 else ''} to review", 12, weight='bold').pack(side='left', padx=12, pady=9)
                self.button(self.face_review_banner, 'Review', self.focus_first_pending_face, True,
                            width=86, height=30).pack(side='right', padx=10, pady=5)
            else:
                self.face_review_banner.pack_forget()
            if not rows:
                self.label(self.face_gallery, 'No people saved yet. Add someone from the camera or a clear photo above.',
                           12, MUTED, wraplength=600).grid(row=0, column=0, sticky='w', pady=12)
            available = self.face_gallery.winfo_width() / self.face_gallery._get_widget_scaling()
            columns = max(1, min(7, int((available - 36) // 100))) if available > 300 else 6
            avatar_size = 82
            for index, row in enumerate(rows):
                column = index % columns
                self.face_gallery.grid_columnconfigure(column, weight=0)
                person = ctk.CTkFrame(self.face_gallery, fg_color='transparent', corner_radius=0)
                person.grid(row=index // columns, column=column, sticky='n', padx=(0, 8), pady=(5, 9))
                image = None
                if row.get('thumbnail'):
                    try:
                        rendered = face_avatar(row['thumbnail'], avatar_size)
                        image = ctk.CTkImage(rendered, size=(avatar_size, avatar_size))
                        self._face_images.append(image)
                    except (OSError, ValueError):
                        pass
                display_name = self.display(row.get('display_name', row['name'])).replace('_', ' ')
                action = (lambda: self.notice.set('Name this captured face below to save it.')) if row.get('pending_id') else (lambda name=row['name']: self.select_face(name))
                avatar = ctk.CTkButton(person, text='' if image else '?', image=image,
                    width=avatar_size, height=avatar_size, corner_radius=avatar_size // 2,
                    border_width=0, fg_color='transparent' if image else SOFT, hover_color=SOFT,
                    text_color=MUTED, font=('Segoe UI', 22, 'bold'), command=action)
                avatar.pack(anchor='center')
                self.label(person, display_name[:22], 12, weight='bold', anchor='center',
                           justify='center', width=90, wraplength=90).pack(pady=(5, 0))
                if row.get('pending_id'):
                    self.label(person, 'Needs a name', 10, GREEN, anchor='center',
                               justify='center', width=90).pack(pady=(1, 3))
                elif row.get('portrait_only'):
                    self.label(person, 'Photo only', 10, MUTED, anchor='center',
                               justify='center', width=90).pack(pady=(1, 3))
                else:
                    sample_count = row['samples']
                    self.label(person, f"{sample_count} sample{'s' if sample_count != 1 else ''}", 10, MUTED,
                               anchor='center', justify='center', width=90).pack(pady=(1, 3))
                if row.get('pending_id'):
                    name_entry = ctk.CTkEntry(person, placeholder_text='Name', width=90, height=32, border_color=LINE)
                    name_entry.pack(pady=(3, 3))
                    self._pending_face_entries[row['pending_id']] = name_entry
                    self.button(person, 'Save name', lambda key=row['pending_id'], entry=name_entry: self.label_captured_face(key, entry.get()),
                                width=90, height=29).pack(pady=2)
                    self.button(person, 'Discard', lambda key=row['pending_id']: self.discard_captured_face(key),
                                True, width=90, height=29).pack(pady=2)
                elif self._people_edit:
                    self.button(person, 'Add photo', lambda name=row['name']: self.select_face(name), True,
                                width=90, height=29).pack(pady=(3, 2))
                    self.button(person, 'Remove', lambda name=row['name'], host=person: self.confirm_remove_face(name, host), True,
                                width=90, height=29).pack(pady=2)
                if row.get('candidate'):
                    try:
                        candidate_image = ctk.CTkImage(face_avatar(row['candidate'], 56), size=(56, 56))
                        self._face_images.append(candidate_image)
                        ctk.CTkLabel(person, text='New sample', image=candidate_image, compound='top', text_color=INK).pack(pady=(5, 2))
                        self.button(person, 'Same person', lambda name=row['name']: self.review_face(name, True), True,
                                    width=90, height=29).pack(pady=2)
                        self.button(person, 'Dismiss', lambda name=row['name']: self.review_face(name, False), True,
                                    width=90, height=29).pack(pady=2)
                    except (OSError, ValueError):
                        pass
        if not self._io.submit('faces_list', lambda: face_id.list_faces() + face_id.inbox.rows(), complete):
            self._faces_refresh_requested = True

    def focus_first_pending_face(self):
        if not self._pending_face_entries:
            return
        first = next(iter(self._pending_face_entries.values()))
        try:
            self.pages['Camera']._parent_canvas.yview_moveto(1.0)
            first.after(120, first.focus_set)
        except (AttributeError, tk.TclError):
            first.focus_set()

    def toggle_discovery(self):
        self.app.face_id.discover_faces = self.discover_people.get() and self._preview
        self._save(face_discovery=self.discover_people.get())

    def label_captured_face(self, key, name):
        name = '_'.join(name.strip().split())
        if not name or len(name)>60 or not name.replace('_','').replace('-','').isalnum():
            self.notice.set('Enter a name using letters, numbers, spaces, hyphens or underscores.')
            return
        def complete(value, error):
            self.notice.set('Could not save this identity. The capture remains available.' if error else 'Face saved for ' + name.replace('_',' ') + '.')
            self._refresh_faces()
        if not self._io.submit('face_label', lambda: self.app.face_id.inbox.label(key, name, self.app.face_id.register_face), complete):
            self.notice.set('A face is being saved. Please wait a moment.')

    def discard_captured_face(self, key):
        def complete(value,error):
            self.notice.set('Could not discard the capture.' if error else 'Unlabelled capture discarded.')
            self._refresh_faces()
        self._io.submit('face_discard', lambda: self.app.face_id.inbox.discard(key), complete)

    def toggle_people_edit(self):
        self._people_edit = not self._people_edit
        self.people_edit_button.configure(text='Done' if self._people_edit else 'Edit people')
        self._face_rows = None
        self._refresh_faces()

    def choose_portrait(self, name):
        path = filedialog.askopenfilename(parent=self.window, title='Choose portrait for ' + name,
            filetypes=[('Portrait photo', '*.jpg *.jpeg *.png *.webp')])
        if not path:
            return
        def complete(value, error):
            self.enrollment_status.set(str(error) if error else 'Portrait saved for ' + name + '.')
            self._refresh_faces()
        if not self._io.submit('portrait_save', lambda: self.app.face_id.set_portrait(name, path), complete):
            self.enrollment_status.set('A portrait is already saving. Please try again in a moment.')

    def toggle_face_candidates(self):
        enabled = self.collect_faces.get()
        self.app.face_id.capture_candidates = enabled and self._preview
        self._save(face_candidates=enabled)

    def review_face(self, name, accept):
        def complete(value, error):
            self.enrollment_status.set('Could not update this appearance.' if error else 'Appearance added to the saved reference.' if accept else 'Candidate dismissed.')
            self._refresh_faces()
        self._io.submit('face_review', lambda: self.app.face_id.review_candidate(name, accept), complete)

    def select_face(self, name):
        self.enroll_name.delete(0, 'end')
        self.enroll_name.insert(0, str(name).replace('_', ' '))
        self.enroll_name.focus_set()
        self.enrollment_status.set('Ready to add another face sample for ' + self.display(str(name).replace('_', ' ')) + '. Choose a photo or save a live camera face.')

    @staticmethod
    def _identity_key(value):
        name = '_'.join(str(value).strip().split())
        if not name or len(name) > 60 or not name.replace('_', '').replace('-', '').isalnum():
            return None
        return name

    def confirm_remove_face(self, name, host):
        if self._enrolling:
            self.enrollment_status.set('Wait for the current face to finish saving before removing a reference.')
            return
        if getattr(host, '_confirming', False):
            return
        host._confirming = True
        panel = ctk.CTkFrame(host, fg_color=SOFT)
        panel.pack(fill='x', padx=10, pady=10)
        self.label(panel, 'Remove this reference?', 12).pack(pady=8)
        def remove():
            def complete(value, error):
                self.enrollment_status.set('Could not remove this face.' if error else 'Saved reference removed for ' + name + '.')
                self._refresh_faces()
            self._io.submit('face_remove', lambda: self.app.face_id.remove_face(name), complete)
        self.button(panel, 'Remove now', remove, True, width=100).pack(side='left', padx=4)
        def cancel():
            panel.destroy()
            host._confirming = False
        self.button(panel, 'Keep', cancel, True, width=65).pack(side='left', padx=4)

    def drop_photo(self, event):
        paths = self.window.tk.splitlist(event.data)
        if len(paths) != 1:
            self.enrollment_status.set('Drop one photo at a time.')
            return 'copy'
        self.enroll_photo(paths[0])
        return 'copy'

    def _start_enrollment(self, message):
        self._enrolling = True
        self.enroll_button.configure(state='disabled', text='Preparing…')
        self.photo_enroll_button.configure(state='disabled')
        self.enroll_name.configure(state='disabled')
        self.enrollment_progress.configure(mode='indeterminate')
        self.enrollment_progress.start()
        self.enrollment_status.set(message)

    def _finish_enrollment(self, message, success=False):
        self._enrolling = False
        self.enrollment_progress.stop()
        self.enrollment_progress.configure(mode='determinate')
        self.enrollment_progress.set(1 if success else 0)
        self.enroll_button.configure(state='normal', text='Save face from camera')
        self.photo_enroll_button.configure(state='normal')
        self.enroll_name.configure(state='normal')
        self.enrollment_status.set(message)
        self._refresh_faces()

    def toggle_preview(self):
        if self._preview:
            self.stop_camera()
            return
        if not self.app.character_profile.allowed('camera'):
            self.notice.set('Camera observations are disabled in Profile & Memory.'); return
        callback = getattr(self.app, '_on_webcam_face', None)
        if not self.app.webcam.start(on_face_id=callback):
            self.notice.set('The camera is still stopping. Try turning it on again in a moment.')
            return
        self._preview = True
        if getattr(self.app, 'face_id', None):
            self.app.face_id.capture_candidates = self.collect_faces.get()
            self.app.face_id.capture_previews = True
            self.app.face_id.discover_faces = self.discover_people.get()
        self.camera_toggle.configure(text='Turn camera off')
        self.camera_state_label.configure(text='Camera on', text_color=GREEN)
        self.camera_preview.configure(image=None, text='Starting your camera…')

    def stop_camera(self):
        self._preview = False
        if getattr(self.app, 'face_id', None):
            self.app.face_id.capture_candidates = False
            self.app.face_id.capture_previews = False
            self.app.face_id.discover_faces = False
        self.app.webcam.release()
        self._camera_image = None
        self.camera_preview.configure(image=None, text='Camera off. Nothing is being captured.')
        self.camera_toggle.configure(text='Turn camera on')
        self.camera_state_label.configure(text='Camera off', text_color=MUTED)

    def enroll_face(self):
        name = self._identity_key(self.enroll_name.get())
        if not name:
            self.enrollment_status.set('Enter a name using letters, numbers, spaces or hyphens.')
            return
        if self._enrolling:
            return
        camera = self.app.webcam
        with camera.face_lock:
            sample = camera.latest_face
            face = sample[1].copy() if sample else None
        if sample is None or time.monotonic()-sample[0] > 1 or face is None or face.size == 0:
            self.enrollment_status.set('No fresh face found. Turn the camera on, then look toward it and try again.')
            return
        self._start_enrollment('Preparing your camera sample. You can keep using the app.')
        def work():
            try:
                from deepface.DeepFace import represent
                result = represent(img_path=face, enforce_detection=False, detector_backend='skip')
                embedding = np.array(result[0]['embedding'])
                self._events.put(('enrolled', (name, embedding, face)))
            except Exception:
                self._events.put(('enroll_error', 'Face enrollment could not finish. Check the recognition model installation and try again.'))
        threading.Thread(target=work, daemon=True).start()

    def enroll_photo(self, path=None):
        if self._enrolling:
            return
        path = path or getattr(self, '_pending_photo', None) or filedialog.askopenfilename(parent=self.window, title='Choose one clear family face',
            filetypes=[('Face photo', '*.png *.jpg *.jpeg *.webp')])
        if not path:
            return
        name = self._identity_key(self.enroll_name.get())
        if not name:
            self._pending_photo = path
            self.photo_enroll_button.configure(text='Save selected photo')
            self.enrollment_status.set('Photo selected. Add a name, then choose Save selected photo.')
            self.enroll_name.focus_set()
            return
        self._pending_photo = None
        self.photo_enroll_button.configure(text='Choose photo')
        self._start_enrollment('Checking photo and preparing the face locally…')
        def work():
            try:
                embedding, preview = self.app.face_id.photo_sample(path)
                self._events.put(('enrolled',(name,embedding,preview)))
            except ValueError:
                self._events.put(('enroll_error','Use a photo with one clear, close face. Group photos and tiny faces cannot be enrolled.'))
            except Exception:
                self._events.put(('enroll_error','Could not process the photo. Check the local recognition model installation.'))
        threading.Thread(target=work,daemon=True).start()

    def _connections(self):
        page = self.pages['Connections']
        self.header(page, 'Bring your day together', 'Choose what Amma can access. Connect, check access, or disconnect here.')
        self.connection_status = tk.StringVar(value=self.calendar.status()['message'])
        self.google_card = self.card(page)
        self.google_card.pack(fill='x')
        self.label(self.google_card, 'Google Calendar', 21, weight='bold').pack(anchor='w', padx=24, pady=(22, 4))
        self.label(self.google_card, 'See upcoming events with read-only access.', 12, MUTED).pack(anchor='w', padx=24)
        self.label(self.google_card, '', 13, textvariable=self.connection_status, wraplength=680).pack(anchor='w', padx=24, pady=18)
        controls = ctk.CTkFrame(self.google_card, fg_color='transparent')
        controls.pack(fill='x', padx=24, pady=(0, 18))
        self.google_connect = self.button(controls, 'Connect Google Calendar', self.connect_google)
        self.google_connect.pack(side='left')
        self.button(controls, 'Test access', lambda: self.calendar_task('test'), True, width=110).pack(side='left', padx=8)
        self.button(controls, 'Disconnect', lambda: self.calendar_task('disconnect'), True, width=110).pack(side='left')
        self.google_setup = ctk.CTkFrame(self.google_card, fg_color=('#f2f6f3', '#28382e'), corner_radius=10)
        self.google_setup.pack(fill='x', padx=24, pady=(0, 20))
        self.label(self.google_setup, 'First-time setup', 13, weight='bold').pack(anchor='w', padx=14, pady=(12, 4))
        self.label(self.google_setup, 'This personal build needs a Google Desktop OAuth client.\nImport its JSON once, then sign in securely in your browser.', 12, MUTED, wraplength=640).pack(anchor='w', padx=14)
        setup_row = ctk.CTkFrame(self.google_setup, fg_color='transparent')
        setup_row.pack(fill='x', padx=14, pady=12)
        self.button(setup_row, 'Import Google client', self.import_google_client, True).pack(side='left')
        self.button(setup_row, 'Setup guide', lambda: webbrowser.open('https://developers.google.com/workspace/calendar/api/quickstart/python'), True, width=110).pack(side='left', padx=8)
        self.button(setup_row, 'Cancel sign-in', self.calendar.cancel, True, width=110).pack(side='left')
        self.calendar_events = tk.StringVar(value='Connect and check access to see your upcoming events.')
        self.label(page, '', 13, MUTED, textvariable=self.calendar_events, wraplength=700).pack(anchor='w', pady=18)
        other = self.card(page)
        other.pack(fill='x', pady=(4, 15))
        self.label(other, 'WhatsApp notifications', 18, weight='bold').pack(anchor='w', padx=24, pady=(18, 5))
        self.label(other, 'Windows notification access needs a native helper.\nIt is not installed in this build; no WhatsApp messages are being collected.', 12, MUTED, wraplength=650).pack(anchor='w', padx=24)
        self.button(other, 'See what’s needed', lambda: self.notice.set('WhatsApp needs the Windows notification-listener helper and your Windows permission. Calendar can be connected now.'), True).pack(anchor='w', padx=24, pady=16)

    def import_google_client(self):
        path = filedialog.askopenfilename(parent=self.window, title='Choose your Google Desktop OAuth client', filetypes=[('Google client JSON', '*.json')])
        if path:
            try:
                result = self.calendar.import_client(path)
                self.connection_status.set(result['message'])
            except (CalendarConnectionError, OSError) as error:
                self.connection_status.set(str(error))

    def connect_google(self):
        if self.calendar.status()['state'] == 'setup_required':
            self.connection_status.set('Start below: import your Google Desktop OAuth client, then choose Connect.')
            return
        self.calendar_task('connect')

    def calendar_task(self, action):
        if self._connection_busy:
            self.connection_status.set('A Calendar action is in progress. Finish or cancel sign-in first.')
            return
        self._connection_busy = True
        self.google_connect.configure(state='disabled')
        self.connection_status.set('Opening Google sign-in…' if action == 'connect' else 'Checking Calendar…')
        def work():
            try:
                result = getattr(self.calendar, {'connect': 'connect', 'test': 'test_connection', 'disconnect': 'disconnect'}[action])()
                events = self.calendar.list_upcoming(5) if action in ('connect', 'test') else []
                message = 'Google Calendar access verified.' if action in ('connect', 'test') else result['message']
                self._events.put(('calendar', (message, events)))
            except (CalendarConnectionError, OSError) as error:
                self._events.put(('calendar', (str(error), [])))
        threading.Thread(target=work, daemon=True).start()

    def _settings(self):
        page = self.pages['Settings']
        self.header(page, 'Make Setta feel like home', 'Your preferences, your pace.')
        layout = ctk.CTkFrame(page, fg_color='transparent')
        layout.pack(fill='x')
        layout.grid_columnconfigure(0, weight=1)
        main = ctk.CTkFrame(layout, fg_color='transparent')
        main.grid(row=0, column=0, sticky='new')
        personality = self.pages['Profile & Memory']
        self.header(personality,'Profile & Memory','Her personality, permissions and what she remembers about you.')
        self.personality_page = self.pages['Personality']
        self.label(self.personality_page, 'Personality', 30, weight='bold').pack(anchor='w', pady=(5, 3))
        self.label(self.personality_page, 'Shape how Setta talks with you. Changes apply to new replies.',
                   15, MUTED, wraplength=760).pack(anchor='w', pady=(0, 20))
        self._personality_preferences(self.personality_page)
        self.button(main,'Open Profile & Memory',lambda:self.show_page('Profile & Memory'),True).pack(anchor='w',pady=(0,15))
        appearance = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=12)
        appearance.pack(fill='x', pady=(0, 15))
        row = ctk.CTkFrame(appearance, fg_color='transparent')
        row.pack(fill='x', padx=20, pady=16)
        self.label(row, 'Appearance', 15, weight='bold').pack(side='left')
        self.dark_mode = tk.BooleanVar(value=self.preferences.values.get('theme') == 'dark')
        self.theme_toggle = ctk.CTkSwitch(row, text='☀  /  ☾', variable=self.dark_mode, text_color=INK,
            progress_color=GREEN, command=lambda: self.set_theme('Dark' if self.dark_mode.get() else 'Light'), width=90)
        self.theme_toggle.pack(side='right')
        self.system_theme = tk.BooleanVar(value=self.preferences.values.get('theme') == 'system')
        self.system_theme_control = ctk.CTkCheckBox(appearance, text='Follow system appearance', variable=self.system_theme,
            command=lambda: self.set_theme('System' if self.system_theme.get() else ('Dark' if self.dark_mode.get() else 'Light')),
            text_color=MUTED, fg_color=GREEN, height=22, checkbox_width=16, checkbox_height=16)
        self.system_theme_control.pack(anchor='w', padx=20, pady=(0, 14))
        self._update_theme_selection()
        language = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=12)
        language.pack(fill='x', pady=(0, 15))
        self.label(language, 'Language & reading', 19, weight='bold').pack(anchor='w', padx=24, pady=(20, 5))
        self.label(language, 'Choose how Malayalam messages appear. Speech is unchanged.', 12, MUTED, wraplength=320).pack(anchor='w', padx=24)
        selected = 'Manglish (Latin letters)' if self.preferences.values['display_script'] == 'manglish' else 'Malayalam (native script)'
        self.script_choice = ctk.CTkOptionMenu(language, values=['Manglish (Latin letters)', 'Malayalam (native script)'],
            command=self.set_script, fg_color=SOFT, button_color=SOFT, button_hover_color=SOFT, text_color=INK, height=40)
        self.script_choice.set(selected)
        self.script_choice.pack(anchor='w', padx=24, pady=16)
        self.language_example = tk.StringVar(value=self.display('സുഖമാണോ?'))
        self.label(language, '', 14, textvariable=self.language_example).pack(anchor='w', padx=24, pady=(0, 20))
        desktop = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=12)
        desktop.pack(fill='x', pady=(0, 15))
        self.label(desktop, 'Desktop presence', 19, weight='bold').pack(anchor='w', padx=24, pady=(20, 8))
        for text, variable, command in [('Show Amma on my desktop', self.visible, self.apply_visibility),
            ('Walk above the taskbar', self.walking, self.apply_walking),
            ('Keep the approved face when resting', self.app._use_approved_face, self.save_likeness)]:
            ctk.CTkSwitch(desktop, text=text, variable=variable, command=command, progress_color=GREEN,
                text_color=INK, font=('Segoe UI', 13)).pack(anchor='w', padx=24, pady=10)
        self.reduced = tk.BooleanVar(value=self.preferences.values['reduced_motion'])
        ctk.CTkSwitch(desktop, text='Reduce app animation', variable=self.reduced,
            command=lambda: self._save(reduced_motion=self.reduced.get()), progress_color=GREEN,
            text_color=INK).pack(anchor='w', padx=24, pady=(10, 22))
        privacy = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=12)
        privacy.pack(fill='x')
        self.label(privacy, 'Conversation & memory', 19, weight='bold').pack(anchor='w', padx=24, pady=(20, 6))
        self.label(privacy, 'Your chat memory stays local. The camera is off until you request it on the Camera page.', 12, MUTED, wraplength=300).pack(anchor='w', padx=24)
        row = ctk.CTkFrame(privacy, fg_color='transparent')
        row.pack(fill='x', padx=24, pady=18)
        self.button(row, 'Export chat memory', self.export_memory, True).pack(side='left')
        self.button(row, 'Mute & stop desktop voice', self.mute, True).pack(anchor='w', pady=(8, 0))
        profile = ctk.CTkFrame(personality, fg_color=SURFACE, corner_radius=12)
        profile.pack(fill='x', pady=(15, 0))
        self.label(profile, 'Amma’s profile', 19, weight='bold').pack(anchor='w', padx=24, pady=(20, 6))
        self.label(profile, 'Change her name, role and how she talks. Changes apply to the next reply.', 12, MUTED, wraplength=300).pack(anchor='w', padx=24)
        data = self.app.character_profile.data if hasattr(self.app.character_profile, 'data') else {}
        self.profile_name = ctk.CTkEntry(profile, height=40, placeholder_text='Name', border_color=LINE)
        self.profile_name.insert(0, self.app.character_profile.name)
        self.profile_name.pack(fill='x', padx=24, pady=(16, 8))
        self.profile_role = ctk.CTkEntry(profile, height=40, placeholder_text='Her role', border_color=LINE)
        self.profile_role.insert(0, data.get('role', 'A caring motherly companion'))
        self.profile_role.pack(fill='x', padx=24, pady=(0, 12))
        self.label(profile, 'How should she speak and behave?', 13, weight='bold').pack(anchor='w', padx=24)
        self.profile_instructions = ctk.CTkTextbox(profile, height=140, fg_color=BG, text_color=INK,
            border_color=LINE, border_width=1, corner_radius=10, wrap='word')
        self.profile_instructions.insert('1.0', data.get('custom_instructions', ''))
        self.profile_instructions.pack(fill='x', padx=24, pady=10)
        self.profile_save_button = self.button(profile, 'Save Amma’s profile', self.save_profile)
        self.profile_save_button.pack(anchor='w', padx=24, pady=(0, 8))
        self.profile_status = tk.StringVar(value='Saved in config/amma.json. Provider keys and voice settings are preserved.')
        self.label(profile, '', 12, MUTED, textvariable=self.profile_status, wraplength=300).pack(anchor='w', padx=24, pady=(0, 20))
        backup = ctk.CTkFrame(profile, fg_color='transparent')
        backup.pack(fill='x', padx=24, pady=12)
        self.button(backup, 'Back up personality', self.export_personality, True).pack(anchor='w')
        self.button(backup, 'Import personality', self.import_personality, True).pack(anchor='w', pady=(8, 0))
        self.profile_import_panel = ctk.CTkFrame(profile, fg_color=SOFT)
        self.profile_import_preview = ctk.CTkTextbox(self.profile_import_panel, height=160, text_color=INK, fg_color=SOFT)
        self.profile_import_preview.pack(fill='x', padx=12, pady=12)
        self.profile_import_preview.configure(state='disabled')
        self.button(self.profile_import_panel, 'Apply imported personality', self.apply_personality_import).pack(side='left', padx=12, pady=12)
        self.button(self.profile_import_panel, 'Cancel', lambda: self.profile_import_panel.pack_forget(), True).pack(side='left', pady=12)
        self._profile_controls(personality)

    def _personality_preferences(self, page):
        """Editable conversational defaults, separate from facts and chat memory."""
        self.personality_layout = ctk.CTkFrame(page, fg_color='transparent')
        self.personality_layout.pack(fill='x', pady=(0, 18))
        self.personality_layout.grid_columnconfigure(0, weight=1)
        self.personality_layout.grid_columnconfigure(1, weight=0)

        settings = ctk.CTkFrame(self.personality_layout, fg_color='transparent')
        settings.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
        self.personality_card = settings

        current = self.app.character_profile.personalization()
        self.personality_menus = {}
        self.personality_choice_buttons = {}
        menus = {
            'reply_length': ('Reply length', 'How much detail should she usually include?',
                             {'Brief': 'brief', 'Balanced': 'balanced', 'Detailed': 'detailed'}),
            'advice_style': ('Advice style', 'Choose whether she checks in before offering advice.',
                             {'Ask me first': 'ask_first', 'Practical advice': 'practical'}),
            'humor': ('Humor', 'Set how often a little humor belongs in the conversation.',
                      {'Off': 'off', 'Rarely': 'rare', 'Sometimes': 'occasional'}),
            'follow_up': ('Follow-up questions', 'Choose how often she should ask a question back.',
                          {'Only when useful': 'only_when_needed', 'More often': 'often'}),
        }
        self.personality_values = {}
        for key, (title, description, choices) in menus.items():
            card = self.card(settings)
            card.pack(fill='x', pady=(0, 12))
            self.label(card, title, 18, weight='bold').pack(anchor='w', padx=20, pady=(16, 2))
            self.label(card, description, 14, MUTED, wraplength=480).pack(anchor='w', padx=20, pady=(0, 11))
            selected = next(label for label, value in choices.items() if value == current[key])
            control = tk.StringVar(value=selected)
            self.personality_menus[key] = control
            self.personality_values[key] = choices
            choice_row = ctk.CTkFrame(card, fg_color='transparent')
            choice_row.pack(fill='x', padx=20, pady=(0, 17))
            self.personality_choice_buttons[key] = {}
            for choice in choices:
                button = ctk.CTkButton(
                    choice_row,
                    text=choice,
                    height=46,
                    corner_radius=9,
                    border_width=1,
                    border_color=LINE,
                    fg_color=SURFACE,
                    text_color=INK,
                    hover_color=('#edf5ef', '#2b3931'),
                    font=('Segoe UI', 14, 'bold'),
                    command=lambda key=key, choice=choice: self._set_personality_choice(key, choice),
                )
                button.pack(side='left', fill='x', expand=True, padx=(0, 6))
                self.personality_choice_buttons[key][choice] = button
            self._style_personality_choices(key)

        actions = ctk.CTkFrame(settings, fg_color='transparent')
        actions.pack(fill='x', pady=(2, 0))
        self.personality_save_button = self.button(
            actions, 'Save preferences', self.save_personality_preferences, height=46)
        self.personality_save_button.pack(side='left')
        self.personality_status = tk.StringVar(
            value='Saved on this device. Preferences are separate from memory facts.')
        self.label(actions, '', 14, MUTED, textvariable=self.personality_status,
                   wraplength=540, justify='left').pack(anchor='w', pady=(10, 0), fill='x')

        self.personality_preview_card = self.card(self.personality_layout)
        self.personality_preview_card.grid(row=0, column=1, sticky='new', pady=(0, 12))
        self.label(self.personality_preview_card, 'LIVE PREVIEW', 12, GREEN, 'bold').pack(
            anchor='w', padx=22, pady=(20, 8))
        self.label(self.personality_preview_card, 'A sample reply with your current choices', 15,
                   MUTED, wraplength=300).pack(anchor='w', padx=22, pady=(0, 14))
        self.personality_preview_text = self.label(
            self.personality_preview_card, '', 16, wraplength=300, justify='left')
        self.personality_preview_text.pack(anchor='w', fill='x', padx=22, pady=(0, 20))
        self._update_personality_preview()
        self.personality_layout.bind('<Configure>', self._layout_personality_preview, add='+')

    def _layout_personality_preview(self, event):
        """Keep the preview beside the controls only when both columns stay readable."""
        wide = event.width >= 920
        if wide:
            self.personality_layout.grid_columnconfigure(1, minsize=320)
            self.personality_preview_card.grid(row=0, column=1, sticky='new', pady=(0, 12))
        else:
            self.personality_layout.grid_columnconfigure(1, minsize=0)
            self.personality_preview_card.grid(row=1, column=0, sticky='ew', pady=(6, 12))

    def _style_personality_choices(self, key):
        selected = self.personality_menus[key].get()
        for choice, button in self.personality_choice_buttons[key].items():
            active = choice == selected
            button.configure(
                fg_color=('#177653', '#21744f') if active else SURFACE,
                text_color='#ffffff' if active else INK,
                border_color=('#177653', '#21744f') if active else LINE,
                hover_color=('#0f5f42', '#286f4e') if active else ('#edf5ef', '#2b3931'),
            )

    def _set_personality_choice(self, key, choice):
        if key not in self.personality_menus or choice not in self.personality_values[key]:
            return
        self.personality_menus[key].set(choice)
        self._style_personality_choices(key)
        self._update_personality_preview()

    def _update_personality_preview(self):
        if not hasattr(self, 'personality_preview_text'):
            return
        values = {key: self.personality_values[key][control.get()]
                  for key, control in self.personality_menus.items()}
        if values['advice_style'] == 'ask_first':
            reply = 'That sounds like a lot to carry. Would you like me to listen, or help think through what to do?'
        else:
            reply = 'That sounds like a lot to carry. We can take it one step at a time. A small first step could make this feel more manageable.'
        if values['reply_length'] == 'brief':
            reply = 'I hear you. What feels most important right now?'
        elif values['reply_length'] == 'detailed':
            reply += ' We can look at the options together, choose one that feels realistic, and adjust as we go.'
        if values['humor'] == 'occasional':
            reply += ' And we can keep it human along the way.'
        elif values['humor'] == 'rare':
            reply += ' (And if it gets too heavy, we can find a small reason to smile.)'
        if values['follow_up'] == 'often' and not reply.endswith('?'):
            reply += ' What would help most right now?'
        self.personality_preview_text.configure(text=reply)

    def save_personality_preferences(self):
        changes = {key: self.personality_values[key][control.get()]
                   for key, control in self.personality_menus.items()}
        self.personality_save_button.configure(state='disabled', text='Saving…')
        def complete(profile, error):
            self.personality_save_button.configure(state='normal', text='Save personality preferences')
            if error:
                self.personality_status.set(str(error) if isinstance(error, ValueError)
                    else 'Could not save these preferences. Please try again.')
                return
            self.app.character_profile = profile
            if self.app.voice_agent:
                self.app.voice_agent.profile = profile
            self.personality_status.set('Saved on this device. New replies will use these preferences.')
        if not self._io.submit('personality_save', lambda: CharacterProfile.save_preferences(
                changes, getattr(self.app, 'profile_path', None)), complete):
            self.personality_save_button.configure(state='normal', text='Save personality preferences')
            self.personality_status.set('A personality preference save is already in progress.')

    def _profile_controls(self,page):
        profile=self.app.character_profile
        profile_data = getattr(profile, 'data', {})
        controls=self.card(page); controls.pack(fill='x',pady=16)
        self.label(controls,'Tone, voice & capabilities',20,weight='bold').pack(anchor='w',padx=24,pady=(20,8))
        self.label(controls,'Strict means firm conversation. It does not enable monitoring or extra computer access.',12,MUTED,wraplength=280).pack(anchor='w',padx=24)
        self.profile_tone=ctk.CTkOptionMenu(controls,values=['calm','playful','firm','strict'],fg_color=GREEN)
        self.profile_tone.set(profile_data.get('tone','calm')); self.profile_tone.pack(anchor='w',padx=24,pady=12)
        self.label(controls,'Speaking speed (0.5–2.0)',12).pack(anchor='w',padx=24)
        self.profile_pace=ctk.CTkEntry(controls,height=36,width=140)
        self.profile_pace.insert(0,str(profile_data.get('speech_delivery',{}).get('pace',1.18)))
        self.profile_pace.pack(anchor='w',padx=24,pady=8)
        self.label(controls,'How should she address you? Leave blank for no pet name.',12).pack(anchor='w',padx=24,pady=8)
        self.profile_addresses={}
        for language,label,default in [('ml-IN','Manglish','mone'),('hi-IN','Hindi','beta'),('en-IN','English','son')]:
            row=ctk.CTkFrame(controls,fg_color='transparent'); row.pack(fill='x',padx=24,pady=4)
            self.label(row,label,12,width=100).pack(side='left')
            entry=ctk.CTkEntry(row,height=34); entry.insert(0,profile_data.get('address_by_language',{}).get(language,default))
            entry.pack(side='left',fill='x',expand=True); self.profile_addresses[language]=entry
        self.permission_vars={}
        for key,label in CharacterProfile.CAPABILITIES.items():
            variable=tk.BooleanVar(value=getattr(profile, 'allowed', lambda name: False)(key)); self.permission_vars[key]=variable
            ctk.CTkSwitch(controls,text=label,variable=variable,text_color=INK,progress_color=GREEN).pack(anchor='w',padx=24,pady=7)
            if key == 'location':
                self.label(controls,
                    'Reads a fresh position only when you ask where you are. Nearby place names are matched offline with GeoNames; precise coordinates are not sent to a geocoding service or saved in chat memory. Windows will also ask for location permission.',
                    13, MUTED, wraplength=280).pack(anchor='w', padx=24, pady=(0, 8))
                self.button(controls, 'Open Windows location settings',
                            self.open_windows_location_settings, True).pack(anchor='w', padx=24, pady=(0, 10))
        self.button(controls,'Save capabilities',self.save_capabilities).pack(anchor='w',padx=24,pady=16)
        self.capability_status=tk.StringVar(value='Permissions apply to the next action. Chat history is still saved when recall is disabled.')
        self.label(controls,'',12,MUTED,textvariable=self.capability_status,wraplength=280).pack(anchor='w',padx=24,pady=(0,18))
        self.label(page,'Available now: local arithmetic, one-shot timers, approved app/document opening and Calculator. Arbitrary app typing, study enforcement and separate companion workspaces are not enabled.',12,MUTED,wraplength=280).pack(anchor='w',pady=8)
        memory=self.card(page); memory.pack(fill='x',pady=16)
        self.label(memory,'What she remembers',20,weight='bold').pack(anchor='w',padx=24,pady=(20,8))
        self.label(memory,'Conversations are stored on this laptop. Each reply receives recent messages and a few relevant older ones. Facts you confirm are saved separately; this does not train the AI model. Selected context is sent to the reply provider.',12,MUTED,wraplength=280).pack(anchor='w',padx=24)
        self.fact_key=ctk.CTkEntry(memory,placeholder_text='Fact name, e.g. home_location',height=38)
        self.fact_key.pack(fill='x',padx=24,pady=(16,8))
        self.fact_value=ctk.CTkEntry(memory,placeholder_text='What should she remember?',height=38)
        self.fact_value.pack(fill='x',padx=24,pady=(0,8))
        self.button(memory,'Save or correct fact',self.save_memory_fact,True).pack(anchor='w',padx=24,pady=8)
        self.facts_host=ctk.CTkFrame(memory,fg_color='transparent'); self.facts_host.pack(fill='x',padx=24,pady=12)
        self.memory_search=ctk.CTkEntry(memory,placeholder_text='Search earlier conversations',height=38)
        self.memory_search.pack(fill='x',padx=24,pady=8)
        self.button(memory,'Refresh / search memory',self.refresh_profile_memory,True).pack(anchor='w',padx=24,pady=8)
        self.memory_results=ctk.CTkTextbox(memory,height=220,wrap='word',fg_color=BG,text_color=INK)
        self.memory_results.pack(fill='x',padx=24,pady=12)
        self.memory_notice=tk.StringVar(value='Removing a saved fact does not erase its original conversation or diagnostic recording.')
        self.label(memory,'',12,MUTED,textvariable=self.memory_notice,wraplength=280).pack(anchor='w',padx=24,pady=(0,20))
        self.refresh_profile_memory()

    def save_capabilities(self):
        values={key:variable.get() for key,variable in self.permission_vars.items()}
        tone=self.profile_tone.get(); pace=self.profile_pace.get()
        address={key:entry.get() for key,entry in self.profile_addresses.items()}
        def complete(profile,error):
            if error:
                self.capability_status.set(str(error) if isinstance(error,ValueError) else 'Could not save capabilities.'); return
            self.app.character_profile=profile
            if self.app.voice_agent: self.app.voice_agent.profile=profile
            if self.app._live_conversation: self.app._live_conversation.profile=profile
            if not profile.allowed('camera'): self.stop_camera()
            self.app.desktop_activity.settings['foreground_app']=bool(profile.data.get('context',{}).get('foreground_app',False) and profile.allowed('desktop_context'))
            if profile.allowed('desktop_context'): self.app.desktop_activity.start()
            else: self.app.desktop_activity.stop()
            self.capability_status.set('Saved. Enabled actions stay bounded; extra permissions are never granted by tone.')
        self._io.submit('capabilities',lambda:CharacterProfile.save_controls(values,tone,getattr(self.app,'profile_path',None),pace=pace,address=address),complete)

    @staticmethod
    def open_windows_location_settings():
        webbrowser.open('ms-settings:privacy-location')

    def refresh_profile_memory(self):
        live=self.app._live_conversation
        if not live or not hasattr(self, 'memory_search'): return
        query=self.memory_search.get().strip()
        def complete(value,error):
            if error: self.memory_notice.set('Could not read memory. Try again.'); return
            facts,history=value
            for widget in self.facts_host.winfo_children(): widget.destroy()
            if not facts: self.label(self.facts_host,'No confirmed facts saved yet.',12,MUTED).pack(anchor='w')
            for fact in facts:
                row=ctk.CTkFrame(self.facts_host,fg_color=SOFT); row.pack(fill='x',pady=4)
                self.label(row,self.display(fact['key']+': '+fact['value']),12,wraplength=490).pack(side='left',padx=10,pady=10)
                self.button(row,'Remove saved fact',lambda key=fact['key']:self.remove_memory_fact(key),True,width=130).pack(side='right',padx=8)
            self.memory_results.configure(state='normal'); self.memory_results.delete('1.0','end')
            self.memory_results.insert('1.0','\n\n'.join(self.display(row['role']+' · '+row['created_at']+'\n'+row['text']) for row in history) or 'No matching conversations.')
            self.memory_results.configure(state='disabled')
            self.memory_notice.set('Local memory: '+str(live.memory.path)+'\nRemoving facts keeps original conversations and diagnostics.')
        self._io.submit('profile_memory',lambda:(live.memory.facts(),live.memory.search(query,limit=20) if query else live.memory.recent(20)),complete)

    def save_memory_fact(self):
        live=self.app._live_conversation; key=self.fact_key.get().strip(); value=self.fact_value.get().strip()
        if not live or not key or len(key)>80 or not value or len(value)>1000:
            self.memory_notice.set('Enter a fact name up to 80 characters and a value up to 1000.'); return
        def save():
            source=live.memory.add_message('profile-editor','user','Remember: '+key+' = '+value)
            live.memory.remember(key,value,source)
        self._io.submit('fact_edit',save,lambda value,error:self.refresh_profile_memory() if not error else self.memory_notice.set('Could not save the fact.'))

    def remove_memory_fact(self,key):
        live=self.app._live_conversation
        self._io.submit('fact_edit',lambda:live.memory.forget_fact(key),lambda value,error:self.refresh_profile_memory() if not error else self.memory_notice.set('Could not remove the saved fact.'))

    def _update_theme_selection(self):
        selected = self.preferences.values.get('theme', 'light')
        self.system_theme.set(selected == 'system')
        if selected != 'system':
            self.dark_mode.set(selected == 'dark')
        self.theme_toggle.configure(state='disabled' if selected == 'system' else 'normal')

    def set_theme(self, value):
        ctk.set_appearance_mode(value.lower())
        self._save(theme=value.lower())
        self._update_theme_selection()
        self._render_messages()

    def export_personality(self):
        path = filedialog.asksaveasfilename(parent=self.window, title='Back up Amma personality', defaultextension='.json', filetypes=[('Personality backup', '*.json')])
        if path:
            self._io.submit('profile_export', lambda: export_profile(path, getattr(self.app, 'profile_path', None)),
                lambda value, error: self.profile_status.set(str(error) if error else 'Personality backed up. Voice settings and chat memory are excluded.'))

    def import_personality(self):
        path = filedialog.askopenfilename(parent=self.window, title='Preview Amma personality backup', filetypes=[('Personality backup', '*.json')])
        if not path:
            return
        def complete(fields, error):
            if error:
                self.profile_status.set(str(error))
                return
            self._import_fields = fields
            self.profile_import_preview.configure(state='normal')
            self.profile_import_preview.delete('1.0', 'end')
            self.profile_import_preview.insert('end', 'Name: ' + fields['name'] + '\nRole: ' + fields['role'] + '\nInstructions: ' + fields['custom_instructions']
                + ('\nPersonality preferences: ' + json.dumps(fields['personalization'], ensure_ascii=False)
                   if fields.get('personalization') else '\nPersonality preferences: current settings will be kept.'))
            self.profile_import_preview.configure(state='disabled')
            self.profile_import_panel.pack(fill='x', padx=24, pady=12)
            self.profile_status.set('Preview only. Apply to save, or cancel to keep your profile.')
        self._io.submit('profile_preview', lambda: preview_profile(path), complete)

    def apply_personality_import(self):
        fields = getattr(self, '_import_fields', None)
        if not fields:
            return
        for entry, value in [(self.profile_name, fields['name']), (self.profile_role, fields['role'])]:
            entry.delete(0, 'end')
            entry.insert(0, value)
        self.profile_instructions.delete('1.0', 'end')
        self.profile_instructions.insert('end', fields['custom_instructions'])
        for key, value in fields.get('personalization', {}).items():
            if key in self.personality_menus:
                choice = next(label for label, stored_value in self.personality_values[key].items()
                              if stored_value == value)
                self._set_personality_choice(key, choice)
        self.profile_import_panel.pack_forget()
        self._import_fields = None
        self.save_profile()

    def save_profile(self):
        changes = {'name': self.profile_name.get().strip(), 'role': self.profile_role.get().strip(),
                   'custom_instructions': self.profile_instructions.get('1.0', 'end').strip()}
        if hasattr(self, 'personality_menus'):
            changes['personalization'] = {key: self.personality_values[key][menu.get()]
                                          for key, menu in self.personality_menus.items()}
        self.profile_save_button.configure(state='disabled', text='Saving…')
        def complete(profile, error):
            self.profile_save_button.configure(state='normal', text='Save Amma’s profile')
            if error:
                self.profile_status.set(str(error) if isinstance(error, ValueError) else 'Could not save the profile. Please try again.')
                return
            self.app.character_profile = profile
            if self.app.voice_agent:
                self.app.voice_agent.profile = profile
            self.window.title('Setta — Home with ' + profile.name)
            self.app.root.title(profile.name + ' — SETTA')
            self.home_identity.configure(text='●  ' + profile.name + ' is here')
            self.conversation_title.configure(text='Chat history')
            self.profile_status.set('Profile saved. The next conversation reply will use these instructions.')
        if not self._io.submit('profile_save', lambda: CharacterProfile.save_personality(changes, getattr(self.app, 'profile_path', None)), complete):
            self.profile_save_button.configure(state='normal', text='Save Amma’s profile')
            self.profile_status.set('A profile save is already in progress.')

    def set_script(self, value):
        self._save(display_script='manglish' if value.startswith('Manglish') else 'native')
        self.language_example.set(self.display('സുഖമാണോ?'))
        self._render_messages()
        self.notice.set('Display preference saved. Voice pronunciation is unchanged.')

    def _save(self, **values):
        self.preferences.values = {**self.preferences.values, **values}
        self._settings_dirty = True
        self._flush_settings()

    def _flush_settings(self):
        if not self._settings_dirty:
            return
        snapshot = dict(self.preferences.values)
        def complete(value, error):
            if error:
                self.notice.set('Your settings could not be saved. Check access to the data folder.')
            self._flush_settings()
        if self._io.submit('settings', lambda: self.preferences.persist(snapshot), complete):
            self._settings_dirty = False

    def apply_visibility(self):
        self._save(desktop_visible=self.visible.get())
        if self.visible.get():
            self.app.root.deiconify()
            if self.walking.get():
                self.app._trigger_walk()
        else:
            self.app._stop_walk()
            self.app.root.withdraw()

    def apply_walking(self):
        self._save(walking=self.walking.get())
        self.app._trigger_walk() if self.walking.get() and self.visible.get() else self.app._stop_walk()

    def save_likeness(self):
        self._save(approved_likeness=self.app._use_approved_face.get())

    def walk(self):
        self.visible.set(True)
        self.walking.set(True)
        self._save(desktop_visible=True, walking=True)
        self.app.root.deiconify()
        self.app._trigger_walk()

    def stay(self):
        self.walking.set(False)
        self._save(walking=False)
        self.app._play_mother('idle', '')

    def preview_expression(self, state):
        self.walking.set(False)
        self._save(walking=False)
        self.app._play_mother(state, '')

    def mute(self):
        if self.app.voice_agent:
            self.app.voice_agent.muted = True
            self.app.voice_agent.stop()
        self.notice.set('Desktop voice stopped and muted. Stop the browser microphone there if it is open.')

    def export_memory(self):
        live = self.app._live_conversation
        if not live:
            self.notice.set('No conversation memory is available in this session.')
            return
        path = filedialog.asksaveasfilename(parent=self.window, title='Export your chat memory', defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            self.notice.set('Exporting chat memory…')
            def complete(value, error):
                self.notice.set('Could not export to that location. Try another folder.' if error else 'Chat memory exported.')
            self._io.submit('memory_export', lambda: live.memory.export(Path(path)), complete)

    def show_page(self, name):
        if name not in self.pages:
            name = 'Home'
        if self._preview and name != 'Camera':
            self.stop_camera()
        self.active_page = name
        # ScrollableFrame.tkraise() raises its inner content, not its outer
        # window. Map exactly one ordinary page host instead of stacking pages.
        for key, host in self.page_hosts.items():
            if key == name:
                host.grid()
            else:
                host.grid_remove()
        for key, nav in self.nav.items():
            nav.configure(fg_color=SOFT if key == name else 'transparent', text_color=GREEN if key == name else MUTED)
        if name == 'Camera':
            self._refresh_faces()
        if name == 'Personality':
            self.refresh_personality_preferences()
        if name == 'Profile & Memory':
            self.refresh_profile_memory()
        if name == 'Conversation':
            if not self.pending:
                self._refresh_history()
            self.composer.focus_set()

    def show(self, page='Home'):
        self.window.deiconify()
        self.window.lift()
        self.show_page(page)

    def refresh_personality_preferences(self):
        if not hasattr(self, 'personality_menus'):
            return
        profile = self.app.character_profile
        profile.refresh()
        current = profile.personalization()
        for key, menu in self.personality_menus.items():
            choice = next(label for label, value in self.personality_values[key].items()
                          if value == current[key])
            self._set_personality_choice(key, choice)
        self._update_personality_preview()

    def hide(self):
        if self._preview:
            self.stop_camera()
        self.window.withdraw() if self.visible.get() else self.window.iconify()

    def _schedule(self, delay, callback):
        if not self.closed:
            self._jobs.append(self.window.after(delay, callback))
            self._jobs = self._jobs[-5:]

    def _animate_avatar(self):
        if self.closed:
            return
        if self.active_page == 'Home' and self.window.state() == 'normal' and not self.reduced.get():
            state = getattr(self.app, 'state', 'idle')
            frames = getattr(self.app, 'frames', {}).get(state, [])
            if frames and state not in ('idle', 'review', 'voice_thinking', 'voice_listening'):
                frame = frames[self._avatar_index % len(frames)]
                key = str(frame)
                if key not in self._avatar_cache:
                    self._avatar_cache[key] = ctk.CTkImage(ImageTk.getimage(frame), size=(260, 365))
                image = self._avatar_cache[key]
            else:
                image = self._rest_avatar
            if image is not self._last_avatar:
                self.avatar.configure(image=image)
                self._last_avatar = image
            self._avatar_index += 1
        elif self.reduced.get():
            if self._last_avatar is not self._rest_avatar:
                self.avatar.configure(image=self._rest_avatar)
                self._last_avatar = self._rest_avatar
        self._schedule(130, self._animate_avatar)

    def _tick(self):
        if self.closed:
            return
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == 'calendar':
                message, events = payload
                self.connection_status.set(message)
                self._connection_busy = False
                self.google_connect.configure(state='normal')
                self.calendar_events.set('\n'.join('• ' + self.display(event.get('summary', 'Untitled event')) + ' — ' + str(event.get('start', {}).get('dateTime', event.get('start', {}).get('date', ''))) for event in events) or 'No upcoming events loaded.')
            elif kind in ('enrolled', 'enroll_error'):
                if kind == 'enrolled':
                    name, embedding, preview = payload
                    self.enrollment_status.set('Saving the face reference on this laptop…')
                    def complete(value, error, saved_name=name):
                        self._finish_enrollment('Could not save the complete face reference. Check the saved-faces list and retry.' if error else
                            'Face saved for ' + self.display(saved_name.replace('_', ' ')) + '.', success=not error)
                    if not self._io.submit('face_save', lambda n=name, e=embedding, p=preview: self.app.face_id.register_face(n, e, p), complete):
                        self._finish_enrollment('Another face save is in progress. Please try again.')
                else:
                    self._finish_enrollment(payload)
        agent = self.app.voice_agent
        listening = getattr(self.app, '_external_handsfree_active', False) or bool(agent and agent.active)
        self._set_text(self.status, 'Listening to you' if listening else 'Thinking about that…' if self.pending else 'Ready when you are · audio muted' if not agent or getattr(agent, 'muted', True) else 'Ready when you are')
        self._set_text(self.camera_status, str(self.app.webcam.status) + ' · ' + getattr(self.app.webcam, 'analysis_status', ''))
        if self._preview and self.active_page == 'Camera':
            camera = self.app.webcam
            with camera.face_lock:
                sample = getattr(camera, 'latest_frame', None)
                frame = sample[1].copy() if sample and time.monotonic()-sample[0] < 2 else None
            if frame is not None:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                preview_width = max(240, min(480, self.camera_card.winfo_width() - 32))
                preview_height = max(150, round(preview_width * 9 / 16))
                self.camera_preview.configure(width=preview_width, height=preview_height)
                image = ImageOps.contain(image, (preview_width, preview_height), method=Image.Resampling.LANCZOS)
                background = '#202a25' if ctk.get_appearance_mode() == 'Dark' else '#e6f2eb'
                preview = Image.new('RGB', (preview_width, preview_height), background)
                preview.paste(image, ((preview_width-image.width)//2, (preview_height-image.height)//2))
                self._camera_image = ctk.CTkImage(preview, size=(preview_width, preview_height))
                self.camera_preview.configure(image=self._camera_image, text='')
            else:
                self.camera_preview.configure(image=None, text='Waiting for a clear face…')
        if not self.pending and time.monotonic() >= self._next_snapshot:
            self._request_snapshot()
            self._next_snapshot = time.monotonic() + 2
        self._schedule(250, self._tick)

    def close(self):
        self.closed = True
        self.calendar.cancel()
        self.window.after_cancel(self._io_job)
        if self._settings_dirty:
            snapshot = dict(self.preferences.values)
            self._io.submit('final_settings', lambda: self.preferences.persist(snapshot), lambda value, error: None)
        self._io.close()
        for job in self._jobs:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        self.window.destroy()

    @staticmethod
    def _set_text(variable, value):
        if variable.get() != value:
            variable.set(value)
