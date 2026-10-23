"""Aligned animation sequences from the approved mother character artwork."""
from PIL import Image
from pathlib import Path
import cv2
import numpy as np

# Pose order rather than blindly playing a row as a loop.
SEQUENCES = {
    'idle': [0] * 25 + [2] + [0] * 8 + [1] * 8,
    'sleep': [2],
    'walk': [4, 5, 6, 7],
    'wave': [0, 3, 3, 3, 0],
    'love': [12, 12, 13, 13, 14, 14, 12, 12],
    'proud': [1, 15, 15, 1, 15, 15, 1],
    'scold': [8, 8, 9, 10, 9, 10, 8, 8],
    'angry': [11] * 12,
    'talk': [8, 9, 8, 10],
    'voice_listening': [0, 0, 1, 1],
    'voice_thinking': [11, 11, 0, 0],
    'review': [0, 0, 1, 1],
}
# Preserve existing interaction state contracts while replacing feline poses.
SEQUENCES.update(jump=SEQUENCES['proud'], stretch=SEQUENCES['love'],
                 failed=SEQUENCES['love'], run=SEQUENCES['wave'])
ONE_SHOT = {'wave', 'love', 'proud', 'scold', 'angry', 'jump', 'stretch', 'failed', 'run', 'laugh', 'sad', 'concern', 'smile'}


def approved_fullbody(path, size):
    """Extract the existing full-length figure, excluding the adjacent portrait."""
    with Image.open(path) as source:
        pixels = np.array(source.convert('RGBA').crop((1008, 0, 1400, 1024)))
    _, labels, stats, _ = cv2.connectedComponentsWithStats((pixels[:, :, 3] > 200).astype('uint8'))
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    pixels[:, :, 3] = np.where(labels == main, 255, 0).astype('uint8')
    figure = Image.fromarray(pixels)
    figure = figure.crop(figure.getchannel('A').getbbox())
    figure.thumbnail((size[0]-12, size[1]-30), Image.Resampling.LANCZOS)
    # Tk's colour-key overlay cannot blend partial alpha with the desktop.
    # A clean binary silhouette avoids tinted fringes around hair and clothing.
    figure.putalpha(figure.getchannel('A').point(lambda a: 255 if a > 180 else 0))
    frame = Image.new('RGBA', size)
    frame.alpha_composite(figure, ((size[0]-figure.width)//2, size[1]-6-figure.height))
    return frame


def load_poses(path, size=(192, 208)):
    """Use common scale and foot baseline; never scale each pose independently."""
    with Image.open(path) as image:
        sheet = image.convert('RGBA')
    poses = []
    # Generated artwork has uneven row spacing; these are measured separators.
    row_edges = [0, 320, 634, 933, 1240]
    col_edges = [0, 340, 665, 990, 1269]
    for row in range(4):
        for col in range(4):
            cell = sheet.crop((round(col_edges[col] * sheet.width / 1269),
                               round(row_edges[row] * sheet.height / 1240),
                               round(col_edges[col + 1] * sheet.width / 1269),
                               round(row_edges[row + 1] * sheet.height / 1240)))
            pixels = np.array(cell)
            count, labels, stats, _ = cv2.connectedComponentsWithStats((pixels[:, :, 3] > 40).astype('uint8'))
            if count <= 1:
                raise ValueError('Empty mother pose')
            main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            # Remove fragments from neighbours which cross the generated grid.
            pixels[labels != main, 3] = 0
            cell = Image.fromarray(pixels)
            # Ignore almost transparent fringe when locating the character.
            bounds = cell.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
            if bounds is None:
                raise ValueError(f'Mother pose {row * 4 + col} is empty')
            poses.append(cell.crop(bounds))
    scale = min((size[0] - 12) / max(p.width for p in poses),
                (size[1] - 30) / max(p.height for p in poses))
    aligned = []
    for pose in poses:
        pose = pose.resize((round(pose.width * scale), round(pose.height * scale)), Image.Resampling.NEAREST)
        frame = Image.new('RGBA', size)
        frame.alpha_composite(pose, ((size[0] - pose.width) // 2, size[1] - 6 - pose.height))
        aligned.append(frame)
    return aligned


def animation_frames(path, size=(192, 208)):
    poses = load_poses(path, size)
    frames = {state: [poses[index] for index in sequence] for state, sequence in SEQUENCES.items()}
    walk_path = Path(path).with_name('mother-walk-v3.png')
    if walk_path.exists():
        frames['walk'] = load_walk_cycle(walk_path, size)
    standing_path = Path(path).with_name('mother-standing-front-v5.png')
    if standing_path.exists():
        standing = load_walk_cycle(standing_path, size, bob=False)
        sequences = {
            'idle': [0]*25 + [2] + [0]*8 + [1]*8,
            'sleep': [2], 'wave': [0, 3, 3, 3, 0],
            'love': [4]*8 + [1]*4, 'proud': [5, 5, 1, 5, 5, 1],
            'scold': [7, 6, 6, 7, 6, 6], 'angry': [7]*12,
            'talk': [1, 6, 1, 6], 'review': [0, 1],
            'voice_listening': [0, 1], 'voice_thinking': [0, 2, 0],
        }
        for state, sequence in sequences.items():
            frames[state] = [standing[index] for index in sequence]
        for alias, state in {'jump':'proud', 'stretch':'love', 'failed':'love', 'run':'wave'}.items():
            frames[alias] = frames[state]
    approved_path = Path(path).with_name('mother-fullbody-emotions-v7.png')
    if approved_path.exists():
        approved = load_walk_cycle(approved_path, size, bob=False, normalize=True)
        sequences = {
            'idle': [0]*40, 'smile': [0]*12,
            'love': [0, 2, 2, 2, 2, 0], 'proud': [0, 3, 3, 0, 3, 3, 0],
            'sad': [0, 4, 4, 4, 4, 0], 'concern': [0, 5, 5, 5, 0],
            'scold': [5, 6, 6, 5, 6, 6], 'angry': [6]*12,
            'talk': [5, 6, 5, 6], 'review': [0]*8,
            'voice_listening': [0]*8, 'voice_thinking': [5]*8,
        }
        for state, sequence in sequences.items():
            frames[state] = [approved[index] for index in sequence]
        # Keep every legacy state on the approved identity too.
        frames['wave'] = frames['love']
        frames['sleep'] = frames['sad']
        for alias, state in {'jump':'proud', 'stretch':'love', 'failed':'concern', 'run':'love'}.items():
            frames[alias] = frames[state]
    motion_path = Path(path).with_name('mother-motion-v8.png')
    if motion_path.exists():
        motion = load_walk_cycle(motion_path, size, bob=False, rows=3,
                                 edges=[0, 380/1024, 704/1024, 1], normalize=True)
        frames['laugh'] = [motion[i] for i in [0, 0, 1, 1, 2, 2, 1, 3, 3]]
        frames['walk'] = motion[4:12]
    talking_path = Path(path).with_name('mother-conversation-v9.png')
    face_corrected_path = Path(path).with_name('mother-conversation-v10.png')
    if face_corrected_path.exists():
        talking_path = face_corrected_path
    if talking_path.exists():
        frames['talk'] = load_walk_cycle(talking_path, size, bob=False, normalize=False,
                                         resampling=Image.Resampling.LANCZOS)
        for index, frame in enumerate(frames['talk']):
            frame.putalpha(frame.getchannel('A').point(lambda alpha: 255 if alpha > 180 else 0))
            bounds = frame.getchannel('A').getbbox()
            if bounds:
                aligned = Image.new('RGBA', size)
                aligned.alpha_composite(frame, (0, size[1]-6-bounds[3]))
                frames['talk'][index] = aligned
        if face_corrected_path.exists():
            frames['conversation_rest'] = [frames['talk'][0]]
    return frames


def load_walk_cycle(path, size=(144, 160), bob=True, rows=2, edges=None, normalize=False,
                    resampling=Image.Resampling.NEAREST):
    with Image.open(path) as image:
        sheet = image.convert('RGBA')
    cells = []
    edges = edges or [i/rows for i in range(rows+1)]
    for row in range(rows):
        for col in range(4):
            cell = sheet.crop((col * sheet.width // 4, round(edges[row]*sheet.height),
                               (col + 1) * sheet.width // 4, round(edges[row+1]*sheet.height)))
            pixels = np.array(cell)
            _, labels, stats, _ = cv2.connectedComponentsWithStats((pixels[:, :, 3] > 40).astype('uint8'))
            main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            pixels[labels != main, 3] = 0
            cell = Image.fromarray(pixels)
            cells.append(cell.crop(cell.getchannel('A').getbbox()))
    scale = min((size[0]-12)/max(c.width for c in cells), (size[1]-30)/max(c.height for c in cells))
    frames = []
    for index, cell in enumerate(cells):
        if normalize:
            scale = min((size[0]-12)/cell.width, (size[1]-30)/cell.height)
        cell = cell.resize((round(cell.width*scale), round(cell.height*scale)), resampling)
        # Generated PNGs have semi-transparent coloured background fringes.
        # Windows colour-key overlays need a binary alpha silhouette.
        cell.putalpha(cell.getchannel('A').point(lambda alpha: 255 if alpha > 200 else 0))
        frame = Image.new('RGBA', size)
        # Passing poses rise slightly as the planted leg straightens.
        rise = 1 if bob and index in (2, 6) else 0
        frame.alpha_composite(cell, ((size[0]-cell.width)//2, size[1]-6-cell.height-rise))
        frames.append(frame)
    return frames

