"""Display portraits are independent from biometric enrollment."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

class PeopleAlbum:
    def __init__(self, folder):
        self.folder=Path(folder)
        self.index=self.folder/'people.json'
    def names(self):
        try:
            values=json.loads(self.index.read_text(encoding='utf-8'))
            return [v for v in values if isinstance(v,str) and 0<len(v)<=60] if isinstance(values,list) else []
        except (OSError,ValueError):
            return []
    def path(self,name):
        return self.folder/(hashlib.sha256(name.casefold().encode()).hexdigest()[:24]+'.jpg')
    def rows(self):
        return [dict(name=n, thumbnail=self.path(n).read_bytes(), samples=0, candidate=None, portrait_only=True)
                for n in self.names() if self.path(n).exists()]
    def save(self,name,path):
        with Image.open(path) as source:
            if source.width*source.height>25_000_000:
                raise ValueError('Choose a smaller image')
            image=ImageOps.exif_transpose(source).convert('RGB'); image.thumbnail((600,800))
        image.save(self.path(name),quality=94)
    def remove(self,name):
        names=[n for n in self.names() if n!=name]
        temporary=self.index.with_suffix('.tmp')
        temporary.write_text(json.dumps(names,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(self.index)
        self.path(name).unlink(missing_ok=True)
