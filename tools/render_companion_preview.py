"""Offline illustration of the shared bubble geometry and speaking overlay.

This is a rendered UI preview, not a screenshot or proof of audible playback.
"""
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.mother_animation import approved_fullbody
from src.paths import MOTHER_ARTWORK_DIR
from src.thought_bubble import cloud_points, wrap_pages, float_offset
from src.speaking_face import mouth_geometry


def smooth_outline(flat):
    points=list(zip(flat[::2],flat[1::2]));curve=[]
    for i,current in enumerate(points):
        previous=points[i-1];following=points[(i+1)%len(points)]
        for step in range(16):
            t=step/16
            curve.append(tuple(.5*((1-t)**2*previous[k]+(1+2*t-2*t*t)*current[k]+t*t*following[k]) for k in (0,1)))
    return curve


def main():
    out=ROOT/'docs/previews';out.mkdir(parents=True,exist_ok=True)
    factor=3
    font=ImageFont.truetype('C:/Windows/Fonts/Nirmala.ttc',13*factor)
    pose=approved_fullbody(MOTHER_ARTWORK_DIR/'mother-likeness-v6.png',(240,336))
    frames=[]
    for index in range(24):
        image=Image.new('RGBA',(280*factor,432*factor),'#ecefe9')
        image.alpha_composite(pose.resize((240*factor,336*factor),Image.Resampling.LANCZOS),(20*factor,96*factor))
        draw=ImageDraw.Draw(image)
        dy=float_offset(index*.12)
        curve=[(x*factor,(y+dy)*factor) for x,y in smooth_outline(cloud_points(264,78))]
        draw.polygon(curve,fill='#fffdf5')
        draw.line(curve+[curve[0]],fill='#394b3d',width=2*factor,joint='curve')
        for box in [(123.8,91,133.8,101),(137.5,106,142.5,111)]:
            draw.ellipse((box[0]*factor,(box[1]+dy)*factor,box[2]*factor,(box[3]+dy)*factor),fill='#fffdf5',outline='#394b3d',width=2*factor)
        text='Thinking…' if index<8 else "I'm here. Tell me how your day went."
        page=wrap_pages(text,lambda s:font.getlength(s)/factor)[0]
        draw.multiline_text((140*factor,(47+dy)*factor),page,font=font,fill='#253c2e',anchor='mm',align='center',spacing=0)
        if index>=8:
            box=mouth_geometry(index)
            draw.ellipse(tuple(v*factor for v in box),fill='#61362e',outline='#8a5046',width=1)
        frames.append(image.convert('RGB').resize((560,864),Image.Resampling.LANCZOS))
    frames[12].save(out/'thought-bubble-preview.png')
    frames[0].save(out/'thought-bubble-speaking.gif',save_all=True,append_images=frames[1:],duration=120,loop=0)
    print(out/'thought-bubble-preview.png')


if __name__=='__main__': main()

