import threading
import time
import unittest

from src.ui_tasks import UITasks


class UITaskTests(unittest.TestCase):
    def wait_for(self, condition, tasks=None):
        deadline = time.monotonic()+2
        while not condition() and time.monotonic() < deadline:
            if tasks:
                tasks.drain()
            time.sleep(.005)
        self.assertTrue(condition())

    def test_slow_io_does_not_block_submission_and_callbacks_stay_on_ui_thread(self):
        owner = threading.get_ident()
        tasks = UITasks()
        gate = threading.Event()
        entered = threading.Event()
        results = []
        def work():
            self.assertNotEqual(threading.get_ident(), owner)
            entered.set()
            gate.wait(2)
            return 'finished'
        def complete(value, error):
            self.assertEqual(threading.get_ident(), owner)
            results.append((value, error))
        try:
            start = time.perf_counter()
            self.assertTrue(tasks.submit('storage', work, complete))
            self.assertLess(time.perf_counter()-start, .1)
            self.assertTrue(entered.wait(1))
            self.assertFalse(tasks.submit('storage', work, complete))
            tasks.drain()
            self.assertEqual(results, [])
            gate.set()
            self.wait_for(lambda: bool(results), tasks)
            self.assertEqual(results, [('finished', None)])
        finally:
            gate.set()
            tasks.close()
            self.wait_for(lambda: not tasks.alive)

    def test_queue_is_bounded_errors_do_not_kill_worker_and_close_finishes_queued_writes(self):
        tasks = UITasks(capacity=2)
        gate = threading.Event()
        results, writes = [], []
        def failure():
            gate.wait(2)
            raise OSError('busy storage')
        self.assertTrue(tasks.submit('failed', failure, lambda value, error: results.append(error)))
        self.assertTrue(tasks.submit('write', lambda: writes.append('saved'), lambda *args: None))
        self.assertFalse(tasks.submit('overflow', lambda: None, lambda *args: None))
        gate.set()
        self.wait_for(lambda: bool(results) and bool(writes), tasks)
        self.assertIsInstance(results[0], OSError)
        self.assertEqual(writes, ['saved'])
        self.assertTrue(tasks.submit('final-write', lambda: writes.append('last change'), lambda *args: None))
        tasks.close()
        self.assertFalse(tasks.submit('after-close', lambda: None, lambda *args: None))
        self.wait_for(lambda: not tasks.alive)
        self.assertEqual(writes[-1], 'last change')
