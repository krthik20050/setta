import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import sqlite3
import time
import os
import cv2
import numpy as np
import random

from .mother_animation import animation_frames, ONE_SHOT, approved_fullbody
from .desktop_walk import work_area, QuietWalk
from .chat import chat_with_ai
from .live_conversation import LiveConversation
from .sarvam_conversation import RecognizedTurn, mixed_malayalam
from .companion_context import Observation
from .face_id import FaceID
from .webcam import WebcamCapture
from .voice import VoiceAgent
from .sarvam_voice import SarvamVoiceAgent
from .sound_manager import play_action_sound, SoundManagerWindow
from .thought_bubble import draw_cloud, wrap_pages, float_offset, bubble_layout
from .character_profile import CharacterProfile, RecognitionGreeting
from .manglish import to_manglish
from .desktop_context import desktop_observations
from .desktop_activity import DesktopActivity
from .companion_hub import CompanionHub, HubPreferences
from .local_reminders import LocalReminders
from .local_timers import LocalTimers


from .paths import PROJECT_ROOT, ASSETS_DIR, MOTHER_ARTWORK_DIR, KNOWN_FACES_DIR
FACE_SOUND_PATH = r"C:\Users\DELL\Downloads\babu-bhai.mp3"

CELL_W, CELL_H = 240, 336
WINDOW_W, WINDOW_H = 280, 432
SPRITE_TOP = 96
COLS, ROWS = 8, 9

# All 9 Sprite Sheet Row Maps
ROW_IDLE = 0
ROW_SLEEP = 1
ROW_WALK = 2
ROW_JUMP = 3
ROW_WAVE = 4
ROW_FAILED = 5
ROW_STRETCH = 6
ROW_RUN = 7
ROW_REVIEW = 8

WINDOW_MARGIN_X, WINDOW_MARGIN_Y = 20, 60
ANIMATION_INTERVAL_MS = 100
COOLDOWN_SECS = 5.0
OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class PetApp:
    def __init__(self, api_key="", gemini_api_key=""):
        self.api_key = api_key
        self.gemini_api_key = gemini_api_key

        self.root = tk.Tk()
        self.root.title("Amma — SETTA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "#ff00ff")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{sw-WINDOW_W-WINDOW_MARGIN_X}+{sh-WINDOW_H-WINDOW_MARGIN_Y}")

        self.canvas = tk.Canvas(self.root, width=WINDOW_W, height=WINDOW_H,
                                bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()
        self.sprite_id = None
        self._draw_close_button()

        sheet_path = str(MOTHER_ARTWORK_DIR / "mother-expressions-v2.png")
        self.frames = {state: [ImageTk.PhotoImage(frame) for frame in frames]
                       for state, frames in animation_frames(sheet_path, (CELL_W, CELL_H)).items()}
        self.frames['walk_right'] = [ImageTk.PhotoImage(frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
                                     for frame in animation_frames(sheet_path, (CELL_W, CELL_H))['walk']]
        # Keep identity anchored to the exact approved reference, not a later
        # expression generation whose facial proportions may have drifted.
        approved = approved_fullbody(str(MOTHER_ARTWORK_DIR / 'mother-likeness-v6.png'),
                                     (CELL_W, CELL_H))
        self._approved_face = ImageTk.PhotoImage(approved)
        self._use_approved_face = tk.BooleanVar(value=True)
        self._walk_direction = -1
        self.hub_preferences = HubPreferences()
        self._use_approved_face.set(self.hub_preferences.values['approved_likeness'])
        self.hub = None
        self.reminders = LocalReminders(PROJECT_ROOT / 'data' / 'reminders.sqlite')
        self.local_timers = LocalTimers(PROJECT_ROOT/'data/memory/timers.sqlite')
        self._timer_events=queue.Queue()
        self._timer_poll_busy=False
        self._last_reminder_notice = None
        self._hub_chat_busy = False
        self._closing = False

        self.state = "idle"
        self.frame_idx = 0
        self.last_trigger = 0.0
        self.last_user_action = time.time()
        self.is_walking = False
        self._walk_job = None
        self._last_mood = "neutral"

        self.chat_queue = queue.Queue()
        self.bubble_id = None
        self.bubble_bg = None

        self.webcam = WebcamCapture()
        self.webcam.show_cam = False
        self.face_id = FaceID(KNOWN_FACES_DIR, FACE_SOUND_PATH)
        self.face_id.sound_enabled = False

        self.voice_agent = None
        self._handsfree_server = None
        sarvam_key = os.environ.get('SARVAM_API_KEY', '').strip()
        self._live_conversation = LiveConversation(sarvam_key, observations=self._memory_observations,
                                                   camera_frame=self._camera_face_jpeg, camera_request=self._request_camera_preview) if sarvam_key else None
        self.character_profile = CharacterProfile.load()
        self.desktop_activity = DesktopActivity(PROJECT_ROOT/'data/memory/desktop-activity.sqlite',
                                                self.character_profile.data.get('context', {}))
        self.desktop_activity.settings=dict(self.desktop_activity.settings)
        self.desktop_activity.settings['foreground_app']=self.desktop_activity.settings.get('foreground_app',False) and self.character_profile.allowed('desktop_context')
        self.desktop_activity.start()
        self.root.title(self.character_profile.name + " — SETTA")
        self._recognition_greeting = RecognitionGreeting(self.character_profile.greetings)
        if sarvam_key or self.gemini_api_key:
            self.voice_agent = SarvamVoiceAgent(sarvam_key) if sarvam_key else VoiceAgent(self.gemini_api_key)
            self.voice_agent.muted = True
            self.voice_agent.on_state_change = self._voice_on_state
            self.voice_agent.on_text_partial = self._voice_on_text
            self.voice_agent.on_text_final = self._voice_on_final
            if isinstance(self.voice_agent, SarvamVoiceAgent):
                self.voice_agent.on_speech_motion = self._voice_on_motion
                self.voice_agent.on_transcript = self._voice_on_transcript
                self.voice_agent.on_transcript_partial = self._voice_on_transcript_partial
                self.voice_agent.observations = self._memory_observations
                self.voice_agent.camera_frame = self._camera_face_jpeg

        self._cam_window = None
        self._cam_label = None

        self._bubble_job = None
        # Camera capture starts only through an explicit in-app request.
        
        # Start main animation loop and idle behavior scheduler
        self._animate()
        self.root.after(10000, self._idle_behavior_check)
        if self.hub_preferences.values['walking'] and self.hub_preferences.values['desktop_visible']:
            self.root.after(500, self._trigger_walk)
        if not self.hub_preferences.values['desktop_visible']:
            self.root.withdraw()
        self.root.after(150, self._open_hub)
        self.root.after(1000, self._hub_housekeeping)

    def _draw_close_button(self):
        self.canvas.create_text(16, 13, anchor='w', text='Open Setta', fill='#236544',
                                font=('Segoe UI', 10, 'bold'), tags='open_hub')
        self.close_bg = self.canvas.create_oval(
            CELL_W - 28, 2, CELL_W - 4, 26,
            fill="", outline="", width=1.5, tags="close_btn")
        self.close_text = self.canvas.create_text(
            CELL_W - 16, 14, text="\u00d7",
            fill="#ff6b6b", font=("Segoe UI", 15, "bold"),
            tags="close_btn")

    def _on_close_enter(self, event):
        self.canvas.itemconfig(self.close_bg, fill="#6b0000", outline="#ff4444")
        self.canvas.itemconfig(self.close_text, fill="#ffffff")

    def _on_close_leave(self, event):
        self.canvas.itemconfig(self.close_bg, fill="", outline="")
        self.canvas.itemconfig(self.close_text, fill="#ff6b6b")

    def _animate(self):
        if not self.frames:
            self.root.after(ANIMATION_INTERVAL_MS, self._animate)
            return

        animation = 'walk_right' if self.state == 'walk' and self._walk_direction > 0 else self.state
        frames_list = self.frames.get(animation, self.frames["idle"])
        if self.frame_idx >= len(frames_list):
            self.frame_idx = 0
            if self.state in ONE_SHOT and time.monotonic() >= getattr(self, "_manual_until", 0):
                self.state = "walk" if self.is_walking else "idle"
                frames_list = self.frames['walk_right' if self._walk_direction > 0 else 'walk'] if self.is_walking else self.frames['idle']

        if frames_list:
            if self.state == 'walk' and self.is_walking:
                self.frame_idx = int(self._quiet_walk.travelled / 3) % len(frames_list)
            img = frames_list[self.frame_idx]
            if self.state == 'talk':
                motion = getattr(self, '_speech_motion', None)
                if motion:
                    envelope, started = motion
                    index = envelope.frame_at(time.monotonic()-started)
                    img = frames_list[index % len(frames_list)]
                else:
                    img = frames_list[0]
            elif self._use_approved_face.get() and self.state in ('idle', 'review', 'voice_listening', 'voice_thinking'):
                if ('conversation_rest' in self.frames and self.voice_agent
                        and (self.voice_agent.active or getattr(self.voice_agent, 'busy', False))):
                    img = self.frames['conversation_rest'][0]
                else:
                    img = self._approved_face
            if self.sprite_id is None:
                self.sprite_id = self.canvas.create_image(
                    getattr(self,'_display_width',WINDOW_W) // 2,
                    SPRITE_TOP + getattr(self,'_bubble_extra',0) + CELL_H // 2, image=img, tags="sprite")
            else:
                self.canvas.itemconfig(self.sprite_id, image=img)
            self.frame_idx += 1
            self.canvas.delete('speaking_mouth')
            self.canvas.tag_raise("close_btn")

        if self.webcam.hand_raised.is_set() and self.state != 'talk' and not self.is_walking and time.monotonic() >= getattr(self, "_manual_until", 0):
            self.webcam.hand_raised.clear()
            now = time.time()
            if now - self.last_trigger > COOLDOWN_SECS:
                self.last_trigger = now
                self.state = "wave"
                self.frame_idx = 0
                self._play_greeting()

        if self.webcam.yawn.is_set() and self.state != 'talk':
            self.webcam.yawn.clear()
            now = time.time()
            if now - self.last_trigger > COOLDOWN_SECS:
                self.last_trigger = now
                play_action_sound("yawn")
                self.show_speech_bubble("Possible yawn. Time for a break?", duration=4)

        mood = self.webcam.current_mood
        if self.state == "idle" and not self.is_walking and time.monotonic() >= getattr(self, "_manual_until", 0):
            if (self.character_profile.data.get('context', {}).get('react_to_expression', False)
                    and mood != self._last_mood and mood != "neutral"):
                now = time.time()
                if now - self.last_trigger > COOLDOWN_SECS:
                    self.last_trigger = now
                    if mood == "happy":
                        self.state = "wave"
                        self.show_speech_bubble("Happy to see you!", duration=3)
                        play_action_sound("happy")
                    elif mood == "sad":
                        self.state = "failed"
                        self.show_speech_bubble("Everything okay?", duration=3)
                        play_action_sound("sad")
                    elif mood == "surprised":
                        self.state = "run"
                        self.show_speech_bubble("Whoa!", duration=3)
                        play_action_sound("surprised")
            self._last_mood = mood

        self.root.after(ANIMATION_INTERVAL_MS, self._animate)

    def _idle_behavior_check(self):
        """Periodically trigger cute random idle animations if Setta is resting."""
        # Stay where the user placed the companion. Animations are explicit.
        self.root.after(12000, self._idle_behavior_check)

    def _play_greeting(self):
        play_action_sound("greeting")

    def _on_webcam_face(self, frame, face_result):
        try:
            with self.webcam.face_lock:
                sample = self.webcam.latest_face
                face_roi = sample[1].copy() if sample is not None else None
            if face_roi is None or face_roi.size == 0:
                return
            self.face_id.identify_async(face_roi, self._on_face_identified)
        except Exception:
            pass

    def _on_face_identified(self, name):
        if self.webcam._stop.is_set() or self.webcam._thread is None:
            return
        self.webcam.face_name = name
        self._face_identified_at = time.monotonic()
        self.root.after(0, lambda: self._consider_amma_greeting(name))
        if name != "Unknown" and name != self.character_profile.greetings.get('owner_face_label'):
            self.face_id.play_sound_once()

    def _consider_amma_greeting(self, name):
        agent = self.voice_agent
        if not isinstance(agent, SarvamVoiceAgent):
            return
        now = time.monotonic()
        settings = self.character_profile.greetings
        if self._recognition_greeting.consider(name, now, busy=agent.busy or agent.active or agent.muted or self.state in ('review','voice_thinking','talk')):
            if agent.say_greeting(settings.get('text', 'Enthaa mone, sukhamaano?'), settings.get('language', 'ml-IN')):
                self._recognition_greeting.mark_greeted(now)

    def _voice_on_state(self, state):
        self.root.after(0, lambda: self._voice_update_state(state))

    def _voice_on_motion(self, motion):
        self.root.after(0, lambda: setattr(self, '_speech_motion', motion))

    def _voice_update_state(self, state):
        self.state = state
        self.frame_idx = 0
        if state == "voice_listening":
            if not getattr(self, '_last_voice_answer', ''):
                self.show_speech_bubble("Listening…", duration=None)
        elif state == 'voice_capturing':
            self.show_speech_bubble('Listening to you…', duration=None)
        elif state == "voice_thinking":
            self._voice_show_text('Thinking…')

    def _voice_on_transcript(self, text):
        self.root.after(0, lambda: self._voice_show_transcript(text))

    def _voice_on_transcript_partial(self, text):
        self.root.after(0, lambda: self._voice_show_transcript(text, final=False))

    def _voice_show_transcript(self, text, final=True):
        self._last_voice_user = text
        self._last_voice_answer = ''
        status = 'Thinking…' if final else 'Listening…'
        self.show_speech_bubble(f'You: {text}\nAmma: {status}', duration=None,follow_latest=not final)

    def _voice_on_text(self, text):
        self.root.after(0, lambda: self._voice_show_text(text))

    def _voice_show_text(self, text):
        user = getattr(self, '_last_voice_user', '')
        self.show_speech_bubble((f'You: {user}\n' if user else '') + f'Amma: {text}', duration=None)

    def _voice_on_final(self, text):
        self.root.after(0, lambda: self._voice_show_final(text))

    def _voice_show_final(self, text):
        self.state = "voice_listening" if self.voice_agent and self.voice_agent.active else "idle"
        self.frame_idx = 0
        self._last_voice_answer = text
        user = getattr(self, '_last_voice_user', '')
        self.show_speech_bubble((f'You: {user}\n' if user else '') + f'Amma: {text}', duration=None)

    def _toggle_voice(self):
        if getattr(self,'_external_handsfree_active',False):
            self.show_speech_bubble('Hands-free is active in the browser. Stop its microphone before switching voice modes.')
            return
        if not self.voice_agent:
            return
        if self.voice_agent.active:
            self.voice_agent.stop()
            self.state = "idle"
            self._clear_bubble()
            self.show_speech_bubble("Voice mode off", duration=2)
        else:
            self.voice_agent.start()

    def run(self):
        self.root.bind_all('<Alt-m>', lambda event: self._toggle_voice())
        self.root.bind_all('<Alt-i>', lambda event: self.voice_agent.interrupt() if isinstance(self.voice_agent, SarvamVoiceAgent) else None)
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<Double-Button-1>", lambda event: self._open_hub())
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<Button-3>", self._show_menu)
        self.canvas.tag_bind("close_btn", "<Button-1>", lambda e: self._exit_app())
        self.canvas.tag_bind("close_btn", "<Enter>", self._on_close_enter)
        self.canvas.tag_bind("close_btn", "<Leave>", self._on_close_leave)
        self.canvas.tag_bind('open_hub', '<Button-1>', lambda event: self._open_hub())
        if self.voice_agent:
            try:
                import keyboard as kb
                kb.add_hotkey('alt+m', self._toggle_voice)
                kb.add_hotkey('alt+i', lambda: self.voice_agent.interrupt() if isinstance(self.voice_agent, SarvamVoiceAgent) else None)
            except Exception:
                pass
        self.root.after(66, self._update_cam_preview)
        self.root.mainloop()

    def _pet_cat(self, event):
        self._play_mother("love", "I'm here with you.")

    def _play_mother(self, state, message):
        self._stop_walk()
        self.last_user_action = time.time()
        self._manual_until = time.monotonic() + 4
        self.state = state
        self.frame_idx = 0
        if message:
            self.show_speech_bubble(message, duration=3)

    def _drag_start(self, event):
        self._stop_walk()
        self.last_user_action = time.time()
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _trigger_nap(self):
        self._stop_walk()
        self.last_user_action = time.time()
        self.state = "sleep"
        self.frame_idx = 0
        self.show_speech_bubble("Taking a cozy nap... 😴", duration=4)

    def _trigger_stretch(self):
        self._stop_walk()
        self.last_user_action = time.time()
        self.state = "stretch"
        self.frame_idx = 0
        self.show_speech_bubble("Take a little break.", duration=3)
        play_action_sound("stretch")

    def _trigger_jump(self):
        self._stop_walk()
        self.last_user_action = time.time()
        self.state = "jump"
        self.frame_idx = 0
        self.show_speech_bubble("Well done!", duration=3)
        play_action_sound("jump")

    def _trigger_roam(self):
        self._trigger_walk()

    def _trigger_walk(self):
        self.last_user_action = time.time()
        if self.is_walking:
            return
        self.is_walking = True
        self.state = "idle"
        self.frame_idx = 0
        self._clear_bubble()
        self._walk_bounds = work_area(self.root.winfo_x() + WINDOW_W // 2,
                                      self.root.winfo_y() + WINDOW_H // 2)
        self._quiet_walk = QuietWalk(self.root.winfo_x(), self._walk_bounds,
                                      WINDOW_W, WINDOW_H, time.monotonic())
        self._step_walk()

    def _stop_walk(self):
        if self._walk_job is not None:
            self.root.after_cancel(self._walk_job)
            self._walk_job = None
        self.is_walking = False
        if self.state == "walk":
            self.state = "idle"
            self.frame_idx = 0

    def _step_walk(self):
        self._walk_job = None
        if not self.is_walking:
            return
        if self.state in ('idle', 'walk'):
            x, y, phase, direction = self._quiet_walk.step(time.monotonic())
            if phase != self.state:
                self.frame_idx = 0
            self.state, self._walk_direction = phase, direction
            self.root.geometry(f"{WINDOW_W}x{WINDOW_H}{x:+d}{y:+d}")
        else:
            self._quiet_walk.previous = time.monotonic()
        self._walk_job = self.root.after(33, self._step_walk)

    def _show_menu(self, event):
        self._stop_walk()
        self.last_user_action = time.time()
        if getattr(self, "_context_menu", None) is not None:
            self._context_menu.destroy()
        menu = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 11),
                       bg="#f4f0e8", fg="#28382f", activebackground="#dce8dc",
                       activeforeground="#173e2a", relief="flat", borderwidth=1)
        self._context_menu = menu
        menu.add_command(label='Open Setta', command=self._open_hub)
        menu.add_separator()
        menu.add_checkbutton(label="Original approved likeness when idle", variable=self._use_approved_face)
        menu.add_command(label="Walk quietly", command=self._trigger_walk)
        menu.add_command(label="Stay here", command=lambda: self._play_mother("idle", ""))
        menu.add_separator()
        menu.add_command(label="Talk to " + self.character_profile.name + "…", command=self._ask_chat)
        if self.voice_agent:
            label = "Voice Chat (Alt+M)" if not self.voice_agent.active else "Stop Voice Chat (Alt+M)"
            menu.add_command(label=label, command=self._toggle_voice)
            if isinstance(self.voice_agent, SarvamVoiceAgent):
                menu.add_command(label="Interrupt reply (Alt+I)", command=self.voice_agent.interrupt)
                menu.add_command(label=("Disable" if self.voice_agent.voice_interruptions else "Enable") + " voice interruptions (headphones)",
                    command=lambda: setattr(self.voice_agent, 'voice_interruptions', not self.voice_agent.voice_interruptions))
            if hasattr(self.voice_agent, 'muted'):
                menu.add_command(label="Enable spoken replies" if self.voice_agent.muted else "Mute spoken replies",
                                 command=self._toggle_spoken_replies)
        
        anim_menu = tk.Menu(menu, tearoff=0)
        anim_menu.add_command(label="Laugh", command=lambda: self._play_mother("laugh", ""))
        anim_menu.add_command(label="Smile", command=lambda: self._play_mother("smile", ""))
        anim_menu.add_command(label="Sad", command=lambda: self._play_mother("sad", ""))
        anim_menu.add_command(label="Concerned", command=lambda: self._play_mother("concern", "Are you okay?"))
        anim_menu.add_command(label="Show love", command=lambda: self._play_mother("love", "I'm here with you."))
        anim_menu.add_command(label="Encourage me", command=lambda: self._play_mother("proud", "You can do this!"))
        anim_menu.add_command(label="Scold me", command=lambda: self._play_mother("scold", "Come on, back to your work!"))
        anim_menu.add_command(label="Look stern", command=lambda: self._play_mother("angry", ""))
        anim_menu.add_command(label="Wave", command=lambda: self._play_mother("wave", "Hello!"))
        anim_menu.add_command(label="Walk with me", command=self._trigger_walk)
        anim_menu.add_command(label="Rest", command=self._trigger_nap)
        anim_menu.add_command(label="Stay here", command=lambda: self._play_mother("idle", ""))
        menu.add_cascade(label="Expressions", menu=anim_menu)

        menu.add_separator()
        camera_menu = tk.Menu(menu, tearoff=0, font=("Segoe UI", 10))
        camera_menu.add_command(label="Show / hide camera", command=self._toggle_cam)
        camera_menu.add_command(label="Enroll my face…", command=self._register_current_face)
        camera_menu.add_command(label="What can you see?", command=self._show_face_observations)
        menu.add_cascade(label="Camera & recognition", menu=camera_menu)
        sound_menu = tk.Menu(menu, tearoff=0, font=("Segoe UI", 10))
        sound_menu.add_command(label="Choose reaction sounds…", command=self._open_sound_manager)
        sound_menu.add_command(label="Toggle recognition greeting", command=self._toggle_face_sound)
        menu.add_cascade(label="Sound settings", menu=sound_menu)
        menu.add_separator()
        menu.add_command(label="Exit Setta", command=self._exit_app)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            # Keep posted menu alive until the next opening; commands belong to it.

    def _show_face_observations(self):
        from tkinter import messagebox
        messagebox.showinfo("Face observations", (
            f"Identity match: {self.webcam.face_name}\n"
            f"Visible activity: {self.webcam.activity.summary}\n\n"
            "Possible yawns use duration and mouth closure, not just an open mouth. "
            "These cues cannot confirm sleep, emotion or concentration."
        ))

    def _register_current_face(self):
        self._open_hub('Camera')
        self.hub.enroll_name.focus_set()

    def _exit_app(self):
        if self._closing:
            return
        self._closing = True
        if self.hub is not None:
            self.hub.close()
        self._stop_walk()
        if self.voice_agent and self.voice_agent.active:
            self.voice_agent.stop()
        try:
            import keyboard as kb
            kb.remove_hotkey('alt+m')
        except Exception:
            pass
        self.webcam.release()
        self.desktop_activity.stop()
        if self._handsfree_server:
            threading.Thread(target=self._handsfree_server.stop,daemon=True).start()
        self.root.withdraw()
        self._finish_shutdown()

    def _finish_shutdown(self):
        storage = getattr(getattr(self, 'hub', None), '_io', None)
        if (self.webcam._thread is not None and self.webcam._thread.is_alive()) or (storage and storage.alive):
            self.root.after(50, self._finish_shutdown)
        else:
            self.root.destroy()

    def _open_handsfree(self):
        # Legacy hub callbacks now open the native conversation instead.
        self._toggle_voice()

    def _prepare_handsfree(self):
        from .handsfree_server import HandsfreeServer
        if self._handsfree_server is None:
            try:
                self._handsfree_server = HandsfreeServer(os.environ.get('SARVAM_API_KEY',''),
                    observations=self._memory_observations, camera_frame=self._camera_face_jpeg,
                    on_active=lambda active:self.root.after(0,lambda:self._handsfree_active(active)))
                self._handsfree_server.start()
            except OSError:
                self.show_speech_bubble('Hands-free port 8770 is unavailable. Close the older instance and try again.')

    def _handsfree_active(self, active):
        if not self.voice_agent:
            return
        if active == getattr(self,'_external_handsfree_active',False):
            return
        self._external_handsfree_active = active
        if active:
            self._pre_handsfree_muted = self.voice_agent.muted
            self.voice_agent.stop()
            self.voice_agent.muted = True
        else:
            self.voice_agent.muted = getattr(self,'_pre_handsfree_muted',False)

    def _toggle_face_sound(self):
        self.face_id.sound_enabled = not self.face_id.sound_enabled

    def _open_sound_manager(self):
        SoundManagerWindow(self.root)

    def _toggle_cam(self):
        self._open_hub('Camera')
        self.hub.toggle_preview()

    def _update_cam_preview(self):
        try:
            if self.webcam.show_cam and self._cam_window is not None and self._cam_label is not None:
                try:
                    frame = self.webcam.cam_queue.get_nowait()
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb)
                    img.thumbnail((640, 480), Image.LANCZOS)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self._cam_label.imgtk = imgtk
                    self._cam_label.config(image=imgtk)
                except queue.Empty:
                    if not hasattr(self._cam_label, "imgtk"):
                        self._cam_label.config(text=self.webcam.status, fg="white", wraplength=560)
            elif self.webcam.show_cam and self._cam_window is None:
                self._cam_window = tk.Toplevel(self.root)
                self._cam_window.title("Setta Camera")
                self._cam_window.geometry("640x480+{}+{}".format(
                    self.root.winfo_screenwidth() - 660,
                    self.root.winfo_screenheight() - 520))
                self._cam_label = tk.Label(self._cam_window, bg="black")
                self._cam_label.pack(fill=tk.BOTH, expand=True)
                self._cam_window.protocol("WM_DELETE_WINDOW", self._toggle_cam)
            elif not self.webcam.show_cam and self._cam_window is not None:
                self._cam_window.destroy()
                self._cam_window = None
                self._cam_label = None
        except Exception:
            self._cam_window = None
            self._cam_label = None
        self.root.after(66, self._update_cam_preview)

    def _ask_chat(self):
        self._open_hub('Conversation')

    def _request_camera_preview(self):
        def open_preview():
            self._open_hub('Camera')
            if self.hub and not self.hub._preview:
                self.hub.toggle_preview()
        self.root.after(0, open_preview)

    def _open_hub(self, page='Home'):
        if self._closing:
            return
        if self.hub is None:
            self.hub = CompanionHub(self)
        self.hub.show(page)

    def _submit_hub_chat(self, prompt):
        if self._hub_chat_busy:
            return
        self._hub_chat_busy = True
        self._stop_walk()
        self.state = 'review'
        self.frame_idx = 0
        threading.Thread(target=self._chat_response, args=(prompt,), daemon=True).start()

    def _hub_housekeeping(self):
        if self._closing:
            return
        request = PROJECT_ROOT / 'runtime' / '.open-hub'
        if request.exists():
            try:
                request.unlink()
                self._open_hub()
            except OSError:
                pass
        if self.hub:
            self.hub.poll_reminders()
        if not self._timer_poll_busy:
            self._timer_poll_busy=True
            def read_timers():
                try:
                    for timer in self.local_timers.due(): self._timer_events.put(timer)
                except (OSError,sqlite3.OperationalError):
                    pass
                finally: self._timer_poll_busy=False
            threading.Thread(target=read_timers,daemon=True).start()
        if self.state not in {'talk','voice_capturing','voice_thinking'}:
            try:
                timer=self._timer_events.get_nowait()
                self.show_speech_bubble(timer['title']+'.',duration=12)
            except queue.Empty: pass
        self.root.after(1000, self._hub_housekeeping)

    def _toggle_spoken_replies(self):
        self.voice_agent.muted = not self.voice_agent.muted
        self.show_speech_bubble("Spoken replies muted" if self.voice_agent.muted else "Spoken replies enabled", duration=2)

    def _chat_response(self, prompt):
        import re
        if self._live_conversation is None:
            reply = 'Sarvam is not configured. Add SARVAM_API_KEY to connect conversation and memory.'
        else:
            language = 'ml-IN' if re.search(r'[\u0d00-\u0d7f]', prompt) else 'hi-IN' if re.search(r'[\u0900-\u097f]', prompt) else 'en-IN'
            try:
                reply = self._live_conversation.reply(RecognizedTurn(prompt, language, None, mixed_malayalam(prompt)))
            except Exception:
                reply = 'The conversation service could not respond. Please check the connection and try again.'
        self.root.after(0, lambda: self._show_reply(reply))

    def _memory_observations(self):
        self.character_profile.refresh()
        settings = self.character_profile.data.get('context', {})
        observations = desktop_observations({**settings, 'foreground_app': False})
        if settings.get('foreground_app', False) and self.character_profile.allowed('desktop_context'):
            observations += self.desktop_activity.observations()
        if not self.character_profile.allowed('camera') or self.webcam._thread is None or self.webcam._stop.is_set():
            return observations
        observed_at = self.webcam.activity.last_seen
        if observed_at is None:
            return observations
        identity_at = getattr(self,'_face_identified_at',0)
        if self.webcam.face_name != 'Unknown' and time.monotonic()-identity_at<3:
            observations.append(Observation('visible_person_label',self.webcam.face_name,
                'local_enrolled_face_match_not_identity_proof',.6,identity_at))
        return observations + [Observation('visible_face_activity', self.webcam.activity.summary,
                            'camera_temporal_heuristic', .5, observed_at)]

    def _camera_face_jpeg(self):
        if self.webcam._stop.is_set() or self.webcam._thread is None:
            return None
        with self.webcam.face_lock:
            sample = self.webcam.latest_face
            if sample is None or time.monotonic()-sample[0] > 2:
                return None
            crop = sample[1].copy()
        if crop.size == 0:
            return None
        height, width = crop.shape[:2]
        if max(height, width) > 512:
            crop = cv2.resize(crop, (max(1, round(width*512/max(height,width))),
                                     max(1, round(height*512/max(height,width)))))
        ok, encoded = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return encoded.tobytes() if ok else None

    def _show_reply(self, reply):
        self._hub_chat_busy = False
        if self.hub is not None:
            self.hub.receive_reply(reply)
        self.state = "idle"
        self.show_speech_bubble(reply)

    def _resize_for_bubble(self,width,height):
        extra = max(0,height-78)
        previous_width = getattr(self,'_display_width',WINDOW_W)
        previous_extra = getattr(self,'_bubble_extra',0)
        if (width,extra)==(previous_width,previous_extra): return
        self._display_width,self._bubble_extra = width,extra
        x = self.root.winfo_x()-(width-previous_width)//2
        y = self.root.winfo_y()-(extra-previous_extra)
        left,top,right,bottom = work_area(x+width//2,y+(WINDOW_H+extra)//2)
        x = max(left,min(x,right-width))
        y = max(top,min(y,bottom-WINDOW_H-extra))
        self.root.geometry(f'{width}x{WINDOW_H+extra}{x:+d}{y:+d}')
        self.canvas.configure(width=width,height=WINDOW_H+extra)
        if self.sprite_id is not None:
            self.canvas.coords(self.sprite_id,width//2,SPRITE_TOP+extra+CELL_H//2)
        self.canvas.move('close_btn',width-previous_width,0)

    def show_speech_bubble(self, text, duration=5, follow_latest=False):
        from tkinter import font as tkfont
        if self.is_walking:
            self._stop_walk()
        self._clear_bubble(collapse=False)
        bubble_font = tkfont.Font(root=self.root, family="Nirmala UI", size=10)
        self._bubble_font = bubble_font
        script = self.hub_preferences.values.get('display_script', 'manglish')
        display_text = to_manglish(str(text)) if script == 'manglish' else str(text)
        left,top,right,bottom = work_area(self.root.winfo_x(),self.root.winfo_y())
        width,height,pages = bubble_layout(display_text,bubble_font.measure,
            line_height=bubble_font.metrics('linespace'),max_width=min(440,right-left),
            max_height=max(78,min(250,bottom-top-WINDOW_H+78)))
        self._resize_for_bubble(width,height)
        self._bubble_float_y = 0
        started = time.monotonic()
        def animate():
            new_y = float_offset(time.monotonic()-started)
            self.canvas.move('bubble', 0, new_y-self._bubble_float_y)
            self._bubble_float_y = new_y
            self._bubble_animation_job = self.root.after(80, animate)
        def display(index):
            self.canvas.delete("bubble")
            draw_cloud(self.canvas, width, pages[index], bubble_font,height)
            self._bubble_float_y = 0
            self.canvas.tag_raise("close_btn")
            delay = max(3000, int((duration or 3)*1000))
            if index+1 < len(pages):
                self._bubble_job = self.root.after(delay, lambda: display(index+1))
            elif duration is not None:
                self._bubble_job = self.root.after(delay, self._clear_bubble)
        display(len(pages)-1 if follow_latest else 0)
        animate()

    def _clear_bubble(self,collapse=True):
        if getattr(self, "_bubble_animation_job", None) is not None:
            self.root.after_cancel(self._bubble_animation_job)
            self._bubble_animation_job = None
        if getattr(self, "_bubble_job", None) is not None:
            self.root.after_cancel(self._bubble_job)
            self._bubble_job = None
        self.canvas.delete("bubble")
        self.bubble_id = None
        self.bubble_bg = None
        if collapse:
            self._resize_for_bubble(WINDOW_W,78)

