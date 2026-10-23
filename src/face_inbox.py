"""Bounded local face captures awaiting a user-supplied identity label."""
from pathlib import Path
import threading
import time
from uuid import uuid4
import numpy as np
from PIL import Image

class FaceInbox:
    def __init__(self,folder):
        self.folder=Path(folder); self.lock=threading.RLock()
        self.last_capture=-100
    def add(self,embedding,face,now=None):
        import cv2
        stamp=time.monotonic() if now is None else now
        query=np.asarray(embedding,dtype=float)
        if face is None or min(face.shape[:2])<80 or query.ndim!=1 or query.size<16 or not np.isfinite(query).all() or np.linalg.norm(query)==0:
            return None
        gray=cv2.cvtColor(face,cv2.COLOR_BGR2GRAY)
        if not 35<gray.mean()<225 or cv2.Laplacian(gray,cv2.CV_64F).var()<40:
            return None
        with self.lock:
            self.folder.mkdir(parents=True,exist_ok=True)
            existing=list(self.folder.glob('*.npy'))
            for path in existing:
                try:
                    known=np.load(path,allow_pickle=False)
                except (OSError, ValueError):
                    continue
                if known.shape==query.shape and np.linalg.norm(known)>0 and float(known@query/(np.linalg.norm(known)*np.linalg.norm(query)))>.82:
                    return path.stem
            if len(existing)>=12 or stamp-self.last_capture<3:
                return None
            key=uuid4().hex
            image=Image.fromarray(face[:,:,::-1]).convert('RGB'); image.thumbnail((600,800))
            image.save(self.folder/(key+'.jpg'),quality=94)
            with (self.folder/(key+'.tmp')).open('wb') as file: np.save(file,query)
            (self.folder/(key+'.tmp')).replace(self.folder/(key+'.npy'))
            self.last_capture=stamp
            return key
    def rows(self):
        with self.lock:
            return [dict(pending_id=p.stem,name='Who is this?',thumbnail=p.with_suffix('.jpg').read_bytes(),samples=0,candidate=None)
                    for p in sorted(self.folder.glob('*.npy')) if p.with_suffix('.jpg').exists()]
    def discard(self,key):
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key): raise ValueError('Invalid capture')
        with self.lock:
            (self.folder/(key+'.npy')).unlink(missing_ok=True)
            (self.folder/(key+'.jpg')).unlink(missing_ok=True)
    def label(self,key,name,register):
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key): raise ValueError('Invalid capture')
        with self.lock:
            embedding=np.load(self.folder/(key+'.npy'),allow_pickle=False)
            with Image.open(self.folder/(key+'.jpg')) as source:
                preview=np.asarray(source.convert('RGB'))[:,:,::-1].copy()
            register(name,embedding,preview)
            self.discard(key)
