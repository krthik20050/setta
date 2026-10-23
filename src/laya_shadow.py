"""Bounded asynchronous Laya evaluation, isolated from the audible reply path."""
import json
import os
import queue
import subprocess
import threading

from .paths import PROJECT_ROOT

_MODEL_LEASE = threading.Lock()

class LayaShadow:
    def __init__(self):
        self.enabled = os.environ.get('LAYA_SHADOW', '0') == '1'
        self.jobs = queue.Queue(maxsize=1)
        self.process = None
        self.stopped = threading.Event()
        self.lock = threading.Lock()
        self.worker = None

    def submit(self, text, language, journal, turn_id, rule_route):
        if not self.enabled or self.stopped.is_set():
            return
        with self.lock:
            if self.worker is None:
                self.worker = threading.Thread(target=self._run, daemon=True)
                self.worker.start()
        try:
            self.jobs.put_nowait((text, language, journal, turn_id, rule_route))
        except queue.Full:
            journal.event(turn_id, 'decision_shadow_skipped', reason='worker_busy')

    def _run(self):
        if not _MODEL_LEASE.acquire(blocking=False):
            self.enabled = False
            return
        try:
            python = PROJECT_ROOT/'.tools/laya-env/Scripts/python.exe'
            environment = {k:v for k,v in os.environ.items() if not any(secret in k.upper() for secret in ('TOKEN','SECRET','PASSWORD','API_KEY'))}
            environment['HF_HOME'] = str(PROJECT_ROOT/'.tools/laya-model-cache')
            environment['PYTHONIOENCODING'] = 'utf-8'
            # Downloads belong to setup, never a live conversation.
            environment['HF_HUB_OFFLINE'] = '1'
            while not self.stopped.is_set():
                try:
                    text, language, journal, turn_id, rule_route = self.jobs.get(timeout=.2)
                except queue.Empty:
                    continue
                try:
                    with self.lock:
                        if self.stopped.is_set(): return
                        if self.process is None or self.process.poll() is not None:
                            self.process = subprocess.Popen([str(python), str(PROJECT_ROOT/'tools/laya_worker.py')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding='utf-8', env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.process.stdin.write(json.dumps({'text':text, 'language':language})+'\n')
                    self.process.stdin.flush()
                    output = queue.Queue(maxsize=1)
                    process = self.process
                    threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
                    result = json.loads(output.get(timeout=120))
                    route = result.get('route')
                    allowed = {'reply_model','memory_search','camera_observation','desktop_context',
                               'desktop_action','play_media','multi_step_task'}
                    journal.event(turn_id, 'decision_shadow', suggested_route=route if route in allowed else None,
                        rule_route=rule_route, seconds=result.get('seconds'), error_type=result.get('error_type'),
                        applied=False)
                except (OSError, ValueError, queue.Empty) as error:
                    journal.event(turn_id, 'decision_shadow_error', error_type=type(error).__name__)
                    self.enabled = False
                    return
        finally:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=2)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
            _MODEL_LEASE.release()

    def close(self):
        self.stopped.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=3)
