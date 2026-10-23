import tempfile
from pathlib import Path
import unittest

from src.local_reminders import LocalReminders


class ReminderTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parents[1] / 'runtime'
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'reminders.sqlite'
        self.store = LocalReminders(self.path)

    def test_restarts_preserve_pending_and_do_not_repeat_or_burst(self):
        reminder = self.store.create_water(60, now=100)
        self.assertEqual(self.store.due(now=3699), [])
        self.assertEqual(len(self.store.due(now=100000)), 1)
        restarted = LocalReminders(self.path)
        self.assertTrue(restarted.get(reminder['id'])['pending'])
        self.assertEqual(restarted.due(now=200000), [])
        self.assertTrue(restarted.ack(reminder['id'], 'done', now=200000))
        self.assertFalse(restarted.ack(reminder['id'], 'done', now=200001))
        self.assertEqual(restarted.get(reminder['id'])['next_due'], 203600)
        self.assertEqual(restarted.due(now=203599), [])
        self.assertEqual(len(restarted.due(now=203600)), 1)

    def test_snooze_skip_and_pause_resume(self):
        rid = self.store.create_water(1, now=0)['id']
        self.store.due(now=60)
        self.assertTrue(self.store.ack(rid, 'snooze', now=60))
        self.assertEqual(self.store.due(now=359), [])
        self.assertEqual(len(self.store.due(now=360)), 1)
        self.assertTrue(self.store.ack(rid, 'skip', now=361))
        self.assertEqual(self.store.get(rid)['next_due'], 421)
        self.store.set_enabled(rid, False, now=400)
        self.assertEqual(self.store.due(now=1000), [])
        self.store.set_enabled(rid, True, now=1000)
        self.assertEqual(self.store.due(now=1059), [])
        self.assertEqual(len(self.store.due(now=1060)), 1)
        self.store.set_enabled(rid, True, now=1061)
        self.assertTrue(self.store.get(rid)['pending'])

    def test_invalid_input_and_unknown_ids(self):
        for value in [True, 0, -1, 1441, float('nan'), float('inf'), 'oops', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.create_water(value, now=0)
        self.assertEqual(self.store.list(), [])
        self.assertIsNone(self.store.get(999))
        self.assertFalse(self.store.ack(999, now=0))
        with self.assertRaises(ValueError):
            self.store.ack(999, 'proof', now=0)

    def test_separate_store_connections_claim_only_once(self):
        self.store.create_water(1, now=0)
        second = LocalReminders(self.path)
        self.assertEqual(len(self.store.due(now=60)), 1)
        self.assertEqual(second.due(now=60), [])


if __name__ == '__main__':
    unittest.main()
