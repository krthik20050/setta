"""Bounded background I/O; completion callbacks run only when Tk drains results."""
import queue
import threading


class UITasks:
    def __init__(self, capacity=16):
        self._pending = queue.Queue(maxsize=capacity)
        self._done = queue.Queue()
        self._keys = set()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, name='setta-ui-storage', daemon=True)
        self._thread.start()

    def submit(self, key, work, complete):
        if self._closed.is_set() or key in self._keys or len(self._keys) >= self._pending.maxsize:
            return False
        self._keys.add(key)
        self._pending.put_nowait((key, work, complete))
        return True

    def _run(self):
        while not self._closed.is_set() or not self._pending.empty():
            try:
                key, work, complete = self._pending.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                value, error = work(), None
            except Exception as exc:
                value, error = None, exc
            self._done.put((key, complete, value, error))

    def drain(self, limit=8):
        for _ in range(limit):
            try:
                key, complete, value, error = self._done.get_nowait()
            except queue.Empty:
                break
            self._keys.discard(key)
            if not self._closed.is_set():
                complete(value, error)

    def close(self):
        self._closed.set()

    @property
    def alive(self):
        return self._thread.is_alive()
