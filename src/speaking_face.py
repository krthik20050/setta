"""Small native-canvas mouth motion on the unchanged approved mother pose."""


def mouth_geometry(frame_index: int, sprite_left: float = 20, sprite_top: float = 96):
    # Measured mouth center on approved_fullbody(..., (240, 336)).
    opening = (0.6, 1.7, 2.6, 1.2, 0.7, 2.0)[frame_index % 6]
    center_x, center_y = sprite_left + 114, sprite_top + 58
    return center_x-3, center_y-opening/2, center_x+3, center_y+opening/2


def draw_speaking_mouth(canvas, frame_index: int, sprite_left: float = 20, sprite_top: float = 96):
    canvas.delete('speaking_mouth')
    canvas.create_oval(*mouth_geometry(frame_index,sprite_left,sprite_top),
        fill='#61362e',outline='#8a5046',width=.6,tags='speaking_mouth')
