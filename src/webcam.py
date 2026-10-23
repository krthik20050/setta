import cv2
import os
import queue
import threading
import time
from .face_activity import FaceActivity


from .paths import MODELS_DIR
HAND_Y_THRESHOLD = 0.4
FACE_ID_INTERVAL = 30


class WebcamCapture:
    def __init__(self):
        self.hand_raised = threading.Event()
        self.mouth_open = threading.Event()
        self.yawn = threading.Event()
        self.activity = FaceActivity()
        self.latest_face = None
        self.latest_frame = None
        self.face_lock = threading.Lock()
        self.face_detected = threading.Event()
        self.cam_queue = queue.Queue(maxsize=2)
        self.show_cam = True
        self.status = "Camera off"
        self.face_name = "Unknown"
        self.face_emotion = ""
        self._stop = threading.Event()
        self._thread = None
        self._analysis_thread = None
        self.analysis_status = "Not started"
        self._face_id_counter = 0
        self._on_face_id = None
        self._cap = None
        self._hand_detector = None
        self._face_detector = None
        self._emotion_model = None
        self._emotion_lock = threading.Lock()
        self.current_mood = "neutral"
        self._mood_buffer = []

    def start(self, on_face_id=None):
        if self._thread is not None and self._thread.is_alive():
            return not self._stop.is_set()
        self._stop.clear()
        self.status = 'Starting camera...'
        self._on_face_id = on_face_id
        self._thread = threading.Thread(target=self._capture_owned, daemon=True)
        self._thread.start()
        return True

    def release(self):
        # Only the capture thread may close native resources used by inference.
        self._stop.set()
        self.status = 'Camera off'
        with self.face_lock:
            self.latest_face = None
            self.latest_frame = None
        self.activity = FaceActivity()
        self.face_detected.clear()
        self.hand_raised.clear()
        self.yawn.clear()
        self.mouth_open.clear()
        self.face_name = 'Unknown'
        self.face_emotion = ''
        self.current_mood = 'neutral'

    def _capture_owned(self):
        try:
            self._capture()
        except Exception as error:
            self.status = f"Camera unavailable: {error}"
        finally:
            for attr in ("_cap",):
                resource = getattr(self, attr)
                setattr(self, attr, None)
                if resource is not None:
                    try:
                        resource.release() if attr == "_cap" else resource.close()
                    except Exception as error:
                        self.status = f"Camera cleanup: {error}"
            if self._stop.is_set():
                with self.face_lock:
                    self.latest_face = None
                    self.latest_frame = None
                self.activity = FaceActivity()
                self.status = 'Camera off'

    def _update_mood(self, bs):
        if self._emotion_model is not None:  # model mood wins when loaded
            return
        if bs.get("mouthSmileLeft", 0) > 0.15 or bs.get("mouthSmileRight", 0) > 0.15:
            mood = "happy"
        elif bs.get("browDownLeft", 0) > 0.3 or bs.get("browDownRight", 0) > 0.3:
            mood = "sad"
        elif bs.get("jawOpen", 0) > 0.2:
            mood = "surprised"
        else:
            mood = "neutral"
        self._mood_buffer.append(mood)
        if len(self._mood_buffer) > 10:
            self._mood_buffer.pop(0)
            self.current_mood = max(set(self._mood_buffer), key=self._mood_buffer.count)

    _EMOTION_MOOD = {"Happiness": "happy", "Sadness": "sad", "Surprise": "surprised", "Neutral": "neutral"}

    def classify_emotion(self, face_roi):
        """Real emotion via EmotiEffLib (7+1 labels); falls back to blendshape mood."""
        try:
            with self._emotion_lock:
                if self._emotion_model is None:
                    from emotiefflib.facial_analysis import EmotiEffLibRecognizerOnnx  # ponytail: heavy import, load once in webcam thread
                    self._emotion_model = EmotiEffLibRecognizerOnnx(model_name="enet_b0_8_best_afew")
                label, _ = self._emotion_model.predict_emotions(face_roi)
            label = label[0]
            self.face_emotion = label
            self.current_mood = self._EMOTION_MOOD.get(label, "neutral")
        except Exception:
            pass

    def _capture(self):
        # Preview capture must not wait for ML imports, detector loading or inference.
        if self._stop.is_set():
            return
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self._cap = cap
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(0)
            self._cap = cap
        if not cap.isOpened():
            self.status = 'Camera unavailable. Check permissions and close other camera apps.'
            return
        self.status = 'Waiting for camera frames…'
        try:
            while not self._stop.is_set() and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(.03)
                    continue
                frame = cv2.flip(frame, 1)
                with self.face_lock:
                    if self._stop.is_set():
                        break
                    self.latest_frame = (time.monotonic(), frame.copy())
                self.status = 'Camera on'
                if self._analysis_thread is None or not self._analysis_thread.is_alive():
                    if self.analysis_status == 'Not started':
                        self.analysis_status = 'Loading face analysis…'
                        self._analysis_thread = threading.Thread(target=self._analysis_owned, daemon=True)
                        self._analysis_thread.start()
                time.sleep(.015)
        finally:
            self._stop.set()
            if self._analysis_thread:
                self._analysis_thread.join()
            self.analysis_status = 'Not started'

    def _analysis_owned(self):
        try:
            self._analyze_frames()
        except Exception as error:
            self.analysis_status = 'Face analysis unavailable: ' + str(error)
        finally:
            for attr in ('_hand_detector', '_face_detector'):
                detector = getattr(self, attr)
                setattr(self, attr, None)
                if detector:
                    detector.close()

    def _analyze_frames(self):
        import mediapipe as mp
        if self._stop.is_set():
            return
        hand_model = str(MODELS_DIR / "hand_landmarker.task")
        hand_opts = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=hand_model),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            min_hand_detection_confidence=0.7, num_hands=1)
        hand_detector = mp.tasks.vision.HandLandmarker.create_from_options(hand_opts)
        self._hand_detector = hand_detector
        if self._stop.is_set():
            return

        face_model = str(MODELS_DIR / "face_landmarker.task")
        face_opts = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=face_model),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            min_face_detection_confidence=0.5, num_faces=1,
            output_face_blendshapes=True)
        face_detector = mp.tasks.vision.FaceLandmarker.create_from_options(face_opts)
        self._face_detector = face_detector

        self.analysis_status = 'Face analysis ready'
        previous = None
        while not self._stop.is_set():
            with self.face_lock:
                sample = self.latest_frame
                frame = sample[1].copy() if sample and sample[0] != previous else None
            if frame is None:
                time.sleep(.03)
                continue
            previous = sample[0]
            time.sleep(.05)
