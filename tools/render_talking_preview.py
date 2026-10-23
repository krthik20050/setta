"""Offline audiovisual preview of the same audio envelope and sprites as the app."""
from pathlib import Path
import subprocess
import sys
import argparse

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.mother_animation import animation_frames
from src.speech_motion import SpeechMotion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', default='v9')
    args = parser.parse_args()
    audio = ROOT/'assets/mother/voice/experiments/language-switch-latency-2026-10-20/1-ml-IN.wav'
    motion = SpeechMotion.from_wav(audio.read_bytes())
    poses = animation_frames(ROOT/'assets/mother/artwork/mother-expressions-v2.png', (240,336))['talk']
    out = ROOT/'docs/previews'/('talking-'+args.version)
    out.mkdir(parents=True,exist_ok=True)
    frames=[]
    for i in range(round((motion.duration+.6)*10)):
        elapsed=i/10
        frame=Image.new('RGB',(360,440),'#eee9df')
        pose=poses[motion.frame_at(elapsed)]
        frame.paste(pose,(60,70),pose)
        draw=ImageDraw.Draw(frame)
        draw.text((18,18),'Amma - reference-led face and hand poses',fill='#2b382d')
        draw.text((18,39),'Actual approved Malayalam sample; pace 1.18',fill='#435444')
        frames.append(frame)
    frames[0].save(out/'talking-preview.gif',save_all=True,append_images=frames[1:],duration=100,loop=0)
    contact=Image.new('RGB',(240*4,336*2),'#eee9df')
    for i,pose in enumerate(poses):
        contact.paste(pose,((i%4)*240,(i//4)*336),pose)
    contact.save(out/'talking-frames.png')
    # MP4 includes the unchanged approved audio, with no new synthesis call.
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(out/'talking-preview.gif'),
                    '-i',str(audio),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',
                    '-shortest',str(out/'talking-preview.mp4')],check=True)
    print(out/'talking-preview.mp4')


if __name__=='__main__':
    main()
