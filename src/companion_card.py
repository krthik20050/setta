"""Readable portrait and dialogue, separate from the moving desktop sprite."""
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk


class CompanionCard:
    def __init__(self, root, assets):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title('Mother — conversation')
        self.window.attributes('-topmost', True)
        self.window.resizable(False, False)
        self.window.configure(bg='#f4f0e8')
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.window.geometry(f'256x350+{max(0, root.winfo_screenwidth()-280)}+{max(0, root.winfo_screenheight()-450)}')
        tk.Label(self.window, text='Mother', bg='#f4f0e8', fg='#254c3a',
                 font=('Segoe UI', 13, 'bold'), anchor='w').pack(fill='x', padx=14, pady=(10, 4))
        self.photo = tk.Label(self.window, bg='#f4f0e8')
        self.photo.pack()
        self.message = ScrolledText(self.window, bg='#f4f0e8', fg='#28382f',
                                   font=('Segoe UI', 10), wrap='word', height=4,
                                   borderwidth=0, highlightthickness=0)
        self.message.pack(fill='both', expand=True, padx=14, pady=10)
        self.message.insert('1.0', "I'm here with you.")
        self.message.configure(state='disabled')
        self.faces = {}
        with Image.open(assets / 'mother-emotions-v7.png') as source:
            source = source.convert('RGBA')
            for state, index in {'idle':0, 'smile':0, 'love':2, 'proud':2, 'sad':3,
                                 'concern':4, 'scold':5, 'angry':5, 'talk':5}.items():
                col, row = index % 3, index // 3
                face = source.crop((col*source.width//3, row*source.height//2,
                                    (col+1)*source.width//3, (row+1)*source.height//2))
                face.thumbnail((224, 224), Image.Resampling.LANCZOS)
                self.faces[state] = [ImageTk.PhotoImage(face)]
        with Image.open(assets / 'mother-laugh-closeup-v8.png') as source:
            source = source.convert('RGBA')
            self.faces['laugh'] = []
            for col in range(4):
                face = source.crop((col*source.width//4, 0, (col+1)*source.width//4, source.height))
                face.thumbnail((224, 224), Image.Resampling.LANCZOS)
                self.faces['laugh'].append(ImageTk.PhotoImage(face))
        self.update('idle', 0)

    def update(self, state, index):
        frames = self.faces.get(state, self.faces['idle'])
        self.photo.configure(image=frames[(index//2) % len(frames)])

    def say(self, text):
        self.message.configure(state='normal')
        self.message.delete('1.0', 'end')
        self.message.insert('1.0', text)
        self.message.configure(state='disabled')
        self.window.deiconify()

    def toggle(self):
        if self.window.state() == 'withdrawn':
            self.window.deiconify()
        else:
            self.window.withdraw()
