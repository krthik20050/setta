import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import winsound
import ctypes
from pathlib import Path


from .paths import CONFIG_DIR, SOUNDS_DIR
CONFIG_PATH = str(CONFIG_DIR / "sounds.json")
BUILTIN_GREETING = str(SOUNDS_DIR / "greeting.wav")
REACTIONS_MUTED = True

ACTIONS = ["greeting", "face_detected", "happy", "sad", "surprised", "jump", "stretch", "yawn"]

BG = "#0d0d1a"
CARD_BG = "#1a1a30"
CARD_BORDER = "#2a2a4a"
CARD_BORDER_HOVER = "#4a4a7a"
FG = "#e8e8f0"
FG_MUTED = "#666688"
FG_FILE = "#bbbbd0"
GREEN = "#4ade80"
GREEN_DIM = "#2a5a3a"
GRAY_DOT = "#3a3a5c"
GRAY_BADGE = "#333355"
BTN_BROWSE = "#2a2a50"
BTN_PLAY = "#1a4a2e"
BTN_CLEAR = "#4a1a1a"
HOVER_BROWSE = "#3a3a6a"
HOVER_PLAY = "#2a6a3e"
HOVER_CLEAR = "#6a2a2a"
SCROLL_WIDTH = 10


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def play_action_sound(action):
    # Reaction audio stays paused until the owner explicitly resumes it.
    if REACTIONS_MUTED:
        return False
    config = load_config()
    path = config.get(action, "")
    if path and os.path.exists(path):
        _play_file(path)
        return True
    if action == "greeting" and os.path.exists(BUILTIN_GREETING):
        _play_file(BUILTIN_GREETING)
        return True
    return False


def _play_file(path):
    try:
        if path.lower().endswith(".mp3"):
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW(f'open "{path}" alias s', None, 0, None)
            winmm.mciSendStringW("play s from 0", None, 0, None)
        else:
            winsound.PlaySound(path, winsound.SND_ASYNC)
    except Exception:
        pass


def _rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, **kwargs)
    canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, **kwargs)
    canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, **kwargs)
    canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, **kwargs)
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, **kwargs)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, **kwargs)


class HoverButton(tk.Canvas):
    def __init__(self, parent, text, width, height, bg_color, hover_color, fg_color, command, font_size=10, corner=8):
        self._bg = bg_color
        self._hover = hover_color
        self._fg = fg_color
        self._cmd = command
        self._text = text
        self._w = width
        self._h = height
        self._r = corner
        self._fs = font_size
        super().__init__(parent, width=width, height=height,
                         bg=BG, highlightthickness=0, cursor="hand2")
        self._draw(self._bg)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self, color):
        self.delete("all")
        _rounded_rect(self, 0, 0, self._w, self._h, self._r,
                       fill=color, outline="", tags="bg")
        self.create_text(self._w//2, self._h//2, text=self._text,
                         fill=self._fg, font=("Segoe UI", self._fs),
                         tags="text")

    def _on_enter(self, e):
        self._draw(self._hover)

    def _on_leave(self, e):
        self._draw(self._bg)

    def _on_click(self, e):
        if self._cmd:
            self._cmd()


class SoundManagerWindow:
    def __init__(self, parent):
        self.config = load_config()
        self._cards = {}

        self.win = tk.Toplevel(parent)
        self.win.title("Setta Sound Manager")
        self.win.configure(bg=BG)
        self.win.transient(parent)
        self.win.grab_set()

        self.win.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 620, 520
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.win.geometry(f"{w}x{h}+{max(0,x)}+{max(0,y)}")
        self.win.minsize(560, 400)

        header = tk.Frame(self.win, bg=BG)
        header.pack(fill=tk.X, padx=24, pady=(20, 2))
        tk.Label(header, text="Sound Manager",
                 font=("Segoe UI", 18, "bold"), bg=BG, fg=FG).pack(anchor="w")
        tk.Label(header, text="Assign .wav or .mp3 files to each pet action",
                 font=("Segoe UI", 10), bg=BG, fg=FG_MUTED).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self.win, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(body, orient="vertical", command=canvas.yview, width=SCROLL_WIDTH,
                               bg=CARD_BG, troughcolor=BG, activebackground=CARD_BORDER_HOVER)
        scrollable = tk.Frame(canvas, bg=BG)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_cards(scrollable)

        footer = tk.Frame(self.win, bg=BG)
        footer.pack(fill=tk.X, padx=24, pady=(6, 16))
        tk.Button(footer, text="Close", width=14,
                  command=self.win.destroy,
                  font=("Segoe UI", 10),
                  bg=CARD_BG, fg=FG, activebackground=CARD_BORDER_HOVER,
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  padx=20, pady=4).pack(side=tk.RIGHT)

    def _build_cards(self, parent):
        for action in ACTIONS:
            card = self._build_card(parent, action)
            self._cards[action] = card

    def _build_card(self, parent, action):
        label = action.replace("_", " ").title()
        current = self.config.get(action, "")
        has_custom = bool(current and os.path.exists(current))
        filename = Path(current).name if has_custom else ""
        full_path = current if has_custom else ""

        card = tk.Frame(parent, bg=CARD_BG, padx=14, pady=12, relief=tk.FLAT, bd=0)
        card.pack(fill=tk.X, pady=4)

        border = tk.Frame(card, bg=CARD_BORDER, bd=0, highlightthickness=0)
        border.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(border, bg=CARD_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        inner.columnconfigure(1, weight=1)

        dot = tk.Label(inner, text="●", font=("Segoe UI", 14),
                       bg=CARD_BG, fg=GREEN if has_custom else GRAY_DOT)
        dot.grid(row=0, column=0, rowspan=3, padx=(6, 10), sticky="n", pady=2)

        name_row = tk.Frame(inner, bg=CARD_BG)
        name_row.grid(row=0, column=1, sticky="w", pady=(2, 0))
        tk.Label(name_row, text=label, font=("Segoe UI", 12, "bold"),
                 bg=CARD_BG, fg=FG).pack(side=tk.LEFT)

        badge = tk.Label(name_row,
                         text="Custom" if has_custom else "Default",
                         font=("Segoe UI", 8, "bold"),
                         fg="#fff",
                         bg=GREEN if has_custom else GRAY_BADGE,
                         padx=6, pady=1, relief=tk.FLAT)
        badge.pack(side=tk.LEFT, padx=(8, 0))

        display = filename if has_custom else "Built-in default sound"
        fg_display = FG_FILE if has_custom else FG_MUTED
        file_label = tk.Label(inner, text=display, font=("Segoe UI", 10),
                              bg=CARD_BG, fg=fg_display, anchor="w")
        file_label.grid(row=1, column=1, sticky="w", pady=(0, 2))

        path_label = None
        if full_path:
            path_label = tk.Label(inner, text=full_path, font=("Segoe UI", 7),
                                  bg=CARD_BG, fg=FG_MUTED, anchor="w")
            path_label.grid(row=2, column=1, sticky="w")

        btn_col = tk.Frame(inner, bg=CARD_BG)
        btn_col.grid(row=0, column=2, rowspan=3, padx=(8, 0), sticky="e")

        def browse():
            p = filedialog.askopenfilename(
                title=f"Select sound for {label}",
                filetypes=[("Audio files", "*.wav *.mp3"), ("All files", "*.*")])
            if p:
                self.config[action] = p
                save_config(self.config)
                self._rebuild_card(card, action, label)

        def play():
            if not play_action_sound(action):
                messagebox.showinfo("No Sound",
                                    f"No sound set for '{label}'.\nBrowse for a .wav or .mp3 file.")

        def clear():
            self.config.pop(action, None)
            save_config(self.config)
            self._rebuild_card(card, action, label)

        HoverButton(btn_col, "Browse", 78, 28, BTN_BROWSE, HOVER_BROWSE, FG, browse, 10).pack(side=tk.LEFT, padx=2)
        HoverButton(btn_col, "Play", 62, 28, BTN_PLAY, HOVER_PLAY, "#88ddbb", play, 10).pack(side=tk.LEFT, padx=2)
        if has_custom:
            HoverButton(btn_col, "Clear", 52, 28, BTN_CLEAR, HOVER_CLEAR, "#dd8888", clear, 10).pack(side=tk.LEFT, padx=2)

        return {"card": card, "dot": dot, "badge": badge, "file_label": file_label,
                "path_label": path_label, "border": border, "frame": inner}

    def _rebuild_card(self, card, action, label):
        card.destroy()
        new_card = self._build_card(card.master, action)
        self._cards[action] = new_card
        self.win.update_idletasks()
