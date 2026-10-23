import ctypes
import threading
import time
import numpy as np
from pathlib import Path
from .face_inbox import FaceInbox


class FaceID:
    def __init__(self, known_faces_dir, sound_path, sound_cooldown=5.0):
        self.known_faces_dir = Path(known_faces_dir)
        self.inbox = FaceInbox(self.known_faces_dir / 'unlabelled')
        self.discover_faces = False
        self.sound_path = sound_path
        self.sound_cooldown = sound_cooldown
        self.known_face_embeddings = {}
        self._embedding_lock = threading.Lock()
        self.capture_previews = False
        self.capture_candidates = False
        self._preview_seen = {}
        self._candidate_seen = {}
        self._candidate_saved = {}
        self._busy = False
        self.sound_enabled = True
        self._sound_played = False
        self._last_sound_time = 0.0
        self._load_known_faces()

    @property
    def busy(self):
        return self._busy

    def _load_known_faces(self):
        if not self.known_faces_dir.exists():
            self.known_faces_dir.mkdir(parents=True, exist_ok=True)
            return
        for f in self.known_faces_dir.glob("*.npy"):
            try:
                self.known_face_embeddings[f.stem] = np.load(str(f))
            except Exception:
                pass

    def register_face(self, name, embedding, preview=None):
        if not name or len(name)>60 or not name.replace('_','').replace('-','').isalnum():
            raise ValueError('Use a short name with letters, numbers, hyphens or underscores')
        embedding = np.asarray(embedding, dtype=float)
        if embedding.ndim != 1 or embedding.size < 16 or not np.isfinite(embedding).all() or np.linalg.norm(embedding)==0:
            raise ValueError('Invalid face embedding')
        path = self.known_faces_dir / f"{name}.npy"
        with self._embedding_lock:
            self.known_faces_dir.mkdir(parents=True,exist_ok=True)
            previous = self.known_face_embeddings.get(name)
            values = np.atleast_2d(embedding)
            if previous is not None and np.asarray(previous).shape[-1] == embedding.size:
                values = np.vstack((np.atleast_2d(previous), values))[-5:]
            temporary = path.with_suffix('.tmp')
            with temporary.open('wb') as file:
                np.save(file, values)
            temporary.replace(path)
            self.known_face_embeddings[name] = values
            if preview is not None:
                from PIL import Image
                image = Image.fromarray(np.asarray(preview, dtype=np.uint8)[:, :, ::-1]).convert('RGB')
                image.thumbnail((160, 160))
                photo = path.with_suffix('.jpg')
                pending = photo.with_suffix('.jpg.tmp')
                image.save(pending, format='JPEG', quality=90)
                pending.replace(photo)


    def set_portrait(self, name, path):
        """Owner-selected display photo; does not alter identity embeddings."""
        from PIL import Image, ImageOps
        path = Path(path)
        if path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'} or path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('Choose a JPG, PNG or WebP image under 20 MB')
        with Image.open(path) as source:
            if source.width * source.height > 25_000_000:
                raise ValueError('Choose a smaller image')
            image = ImageOps.exif_transpose(source).convert('RGB')
            image.thumbnail((600, 800))
        with self._embedding_lock:
            if name not in self.known_face_embeddings:
                raise ValueError('Choose an enrolled person')
            destination = self.known_faces_dir / (name + '.jpg')
            temporary = destination.with_suffix('.jpg.tmp')
            image.save(temporary, format='JPEG', quality=94)
            temporary.replace(destination)

    def save_missing_preview(self, name, embedding, face, now=None):
        """Fill a missing display image after three clear, strong known matches."""
        if not self.capture_previews or name == 'Unknown' or face is None or min(face.shape[:2]) < 80:
            return False
        import cv2
        stamp = time.monotonic() if now is None else now
        query = np.asarray(embedding, dtype=float)
        if query.ndim != 1 or not np.isfinite(query).all() or np.linalg.norm(query) == 0:
            return False
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        if not 35 < gray.mean() < 225 or cv2.Laplacian(gray, cv2.CV_64F).var() < 40:
            return False
        with self._embedding_lock:
            destination = self.known_faces_dir / (name + '.jpg')
            if name not in self.known_face_embeddings or destination.exists():
                return False
            scores = []
            for label, value in self.known_face_embeddings.items():
                samples = np.atleast_2d(value)
                if samples.shape[1] != query.size:
                    continue
                denominators = np.linalg.norm(samples, axis=1) * np.linalg.norm(query)
                valid = denominators > 0
                if valid.any():
                    scores.append((float(np.max(samples[valid] @ query / denominators[valid])), label))
            scores.sort(reverse=True)
            if not scores or scores[0][1] != name or scores[0][0] < .85 or (len(scores)>1 and scores[0][0]-scores[1][0]<.12):
                self._preview_seen.pop(name, None)
                return False
            count, previous = self._preview_seen.get(name, (0, -100))
            if stamp - previous < 1:
                return False
            count = count + 1 if stamp - previous <= 15 else 1
            self._preview_seen[name] = (count, stamp)
            if count < 3 or not self.capture_previews:
                return False
            from PIL import Image
            image = Image.fromarray(face[:, :, ::-1]).convert('RGB')
            image.thumbnail((600,800))
            temporary = destination.with_suffix('.jpg.tmp')
            image.save(temporary, format='JPEG', quality=94)
            temporary.replace(destination)
            return True

    def list_faces(self):
        with self._embedding_lock:
            rows = []
            for name, value in sorted(self.known_face_embeddings.items()):
                photo = self.known_faces_dir / (name + '.jpg')
                candidate = self.known_faces_dir / 'candidates' / (name + '.jpg')
                rows.append(dict(name=name, samples=len(np.atleast_2d(value)),
                                 thumbnail=photo.read_bytes() if photo.exists() else None,
                                 candidate=candidate.read_bytes() if candidate.exists() else None))
            return rows

    def consider_candidate(self, name, embedding, face, now=None):
        """Collect one reviewed sample per known person, never self-train a match."""
        if not self.capture_candidates or name == 'Unknown':
            return False
        import cv2
        stamp = time.monotonic() if now is None else now
        query = np.asarray(embedding, dtype=float)
        if face is None or min(face.shape[:2]) < 80 or query.ndim != 1 or not np.isfinite(query).all() or np.linalg.norm(query) == 0:
            return False
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        if not 35 < float(gray.mean()) < 225 or cv2.Laplacian(gray, cv2.CV_64F).var() < 40:
            return False
        with self._embedding_lock:
            if name not in self.known_face_embeddings:
                return False
            ranked = []
            for label, reference in self.known_face_embeddings.items():
                samples = np.atleast_2d(reference)
                if samples.shape[1] != query.size:
                    continue
                denom = np.linalg.norm(samples, axis=1) * np.linalg.norm(query)
                valid = denom > 0
                if valid.any():
                    ranked.append((float(np.max(samples[valid] @ query / denom[valid])), label))
            ranked.sort(reverse=True)
            if not ranked or ranked[0][1] != name or ranked[0][0] < .80 or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .12):
                self._candidate_seen.pop(name, None)
                return False
            count, previous = self._candidate_seen.get(name, (0, -100))
            if stamp - previous < 1:
                return False
            count = count + 1 if stamp - previous <= 15 else 1
            self._candidate_seen[name] = count, stamp
            folder = self.known_faces_dir / 'candidates'
            if count < 3 or stamp - self._candidate_saved.get(name, -10000) < 600 or (folder / (name + '.npy')).exists():
                return False
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / (name + '.tmp')).open('wb') as file:
                np.save(file, query)
            (folder / (name + '.tmp')).replace(folder / (name + '.npy'))
            from PIL import Image
            image = Image.fromarray(face[:, :, ::-1]).convert('RGB')
            image.thumbnail((160, 160))
            image.save(folder / (name + '.jpg'), quality=90)
            self._candidate_saved[name] = stamp
            return True

    def review_candidate(self, name, accept):
        if not name or len(name) > 60 or not name.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Invalid face name')
        folder = self.known_faces_dir / 'candidates'
        path = folder / (name + '.npy')
        if accept:
            with self._embedding_lock:
                if name not in self.known_face_embeddings or not path.exists():
                    return False
                embedding = np.load(path, allow_pickle=False)
                from PIL import Image
                with Image.open(folder / (name + '.jpg')) as image:
                    preview = np.asarray(image.convert('RGB'))[:, :, ::-1].copy()
            self.register_face(name, embedding, preview)
        path.unlink(missing_ok=True)
        (folder / (name + '.jpg')).unlink(missing_ok=True)
        return True

    def remove_face(self, name):
        if not name or len(name) > 60 or not name.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Invalid face name')
        with self._embedding_lock:
            (self.known_faces_dir / (name + '.npy')).unlink(missing_ok=True)
            (self.known_faces_dir / (name + '.jpg')).unlink(missing_ok=True)
            self.known_face_embeddings.pop(name, None)
            self._candidate_seen.pop(name, None)
            self._candidate_saved.pop(name, None)
            folder = self.known_faces_dir / 'candidates'
            (folder / (name + '.jpg')).unlink(missing_ok=True)
            (folder / (name + '.npy')).unlink(missing_ok=True)

    def embedding_from_photo(self, path):
        return self.photo_sample(path)[0]

    def photo_sample(self, path):
        from PIL import Image, ImageOps
        path = Path(path)
        if path.suffix.casefold() not in {'.png','.jpg','.jpeg','.webp'} or path.stat().st_size>20*1024*1024:
            raise ValueError('Choose a PNG, JPG or WebP photo under 20 MB')
        with Image.open(path) as source:
            if source.width*source.height > 25_000_000:
                raise ValueError('Choose a smaller photo')
            image = np.asarray(ImageOps.exif_transpose(source).convert('RGB'))[:,:,::-1].copy()
        from deepface.DeepFace import represent
        faces = represent(img_path=image, enforce_detection=True, detector_backend='opencv')
        if len(faces) != 1:
            raise ValueError('Choose a photo with exactly one clear face')
        area = faces[0].get('facial_area',{})
        if min(area.get('w',0),area.get('h',0)) < 60:
            raise ValueError('The face is too small; choose a clearer, closer photo')
        x, y, width, height = (int(area.get(k, 0)) for k in ('x', 'y', 'w', 'h'))
        crop = image[max(0,y):max(0,y)+height, max(0,x):max(0,x)+width].copy()
        return np.asarray(faces[0]['embedding'],dtype=float), crop

    def match_face(self, embedding, threshold=0.4):
        with self._embedding_lock:
            known_faces = list(self.known_face_embeddings.items())
        if not known_faces:
            return "Unknown"
        query = np.asarray(embedding,dtype=float)
        if query.ndim!=1 or not np.isfinite(query).all() or np.linalg.norm(query)==0: return 'Unknown'
        scores=[]
        for name, known_emb in known_faces:
            samples = np.atleast_2d(known_emb)
            if samples.shape[1]!=query.size: continue
            denominators = np.linalg.norm(samples,axis=1)*np.linalg.norm(query)
            valid = denominators>0
            if valid.any():
                scores.append((float(np.max((samples[valid]@query)/denominators[valid])),name))
        scores.sort(reverse=True)
        if not scores or scores[0][0]<threshold: return 'Unknown'
        if len(scores)>1 and scores[0][0]-scores[1][0]<.06: return 'Unknown'
        return scores[0][1]

    def play_sound_once(self):
        if not self.sound_enabled or self._sound_played:
            return False
        now = time.time()
        if now - self._last_sound_time < self.sound_cooldown:
            return False
        self._last_sound_time = now
        self._sound_played = True
        try:
            winmm = ctypes.windll.winmm
            path = self.sound_path.replace("/", "\\")
            winmm.mciSendStringW(f'open "{path}" alias f', None, 0, None)
            winmm.mciSendStringW("play f from 0", None, 0, None)
            return True
        except Exception:
            return False

    def identify_async(self, face_roi, callback):
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._run_deepface, args=(face_roi, callback), daemon=True).start()

    def _run_deepface(self, face_roi, callback):
        try:
            from deepface.DeepFace import represent
            result = represent(img_path=face_roi, enforce_detection=False, detector_backend='skip')
            if isinstance(result, list) and len(result) > 0:
                emb = result[0].get('embedding')
                if emb is not None:
                    name = self.match_face(emb)
                    callback(name)
                    if name == 'Unknown' and self.discover_faces:
                        self.inbox.add(emb, face_roi)
                    self.save_missing_preview(name, emb, face_roi)
                    self.consider_candidate(name, emb, face_roi)
        except Exception:
            pass
        finally:
            self._busy = False
