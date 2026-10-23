import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from src.local_reminders import LocalReminders


def india(hour, minute=0, day=21):
    return datetime(2026, 10, day, hour, minute,
                    tzinfo=timezone(timedelta(hours=5, minutes=30))).timestamp()


class ReminderFeatureTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parents[1] / 'runtime'
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'reminders.sqlite'
        self.store = LocalReminders(self.path)

    def test_multiple_named_reminders_survive_restart_and_archive_keeps_history(self):
        first = self.store.create('Stretch your legs', 30, now=0)
        second = self.store.create('Look away from the screen', 20, now=0)
        self.assertEqual([r['id'] for r in self.store.due(now=1200)], [second['id']])
        self.assertTrue(self.store.ack(second['id'], now=1200))
        self.assertFalse(self.store.ack(second['id'], now=1201))
        self.store.update(first['id'], 'Stand up', 45, now=1200)
        self.assertTrue(self.store.archive(first['id'], now=1300))
        self.assertFalse(self.store.archive(first['id'], now=1301))
        restarted = LocalReminders(self.path)
        self.assertEqual(len(restarted.list()), 1)
        self.assertEqual(len(restarted.list(include_archived=True)), 2)
        self.assertEqual([h['action'] for h in restarted.history(first['id'])], ['archive', 'edit', 'create'])
        self.assertEqual([h['action'] for h in restarted.history(second['id'])], ['done', 'due', 'create'])
        self.assertEqual(restarted.history(second['id'])[0]['source'], 'user_report')
        self.assertEqual(restarted.history(limit=1)[0]['action'], 'archive')
        self.assertEqual(restarted.due(now=100000)[0]['id'], second['id'])

    def test_quiet_hours_use_indian_timezone_and_exact_boundaries(self):
        self.store.set_quiet_hours(True, now=0)
        for stamp, expected in [(india(21, 59), False), (india(22), True),
                                (india(7, 59), True), (india(8), False)]:
            self.assertEqual(self.store.is_quiet(stamp), expected)
        self.assertTrue(LocalReminders(self.path).quiet_hours()['enabled'])
        self.store.set_quiet_hours(True, '12:00', '13:00', now=0)
        self.assertFalse(self.store.is_quiet(india(11, 59)))
        self.assertTrue(self.store.is_quiet(india(12)))
        self.assertFalse(self.store.is_quiet(india(13)))

    def test_quiet_reminders_resume_after_interval_without_morning_burst(self):
        self.store.set_quiet_hours(True, now=0)
        rid = self.store.create('Drink water', 30, now=india(21, 30))['id']
        self.assertEqual(self.store.due(now=india(22)), [])
        self.assertEqual(self.store.get(rid)['next_due'], india(8, 30, day=22))
        self.assertEqual(self.store.due(now=india(8, day=22)), [])
        self.assertEqual(len(self.store.due(now=india(8, 30, day=22))), 1)
        self.assertEqual([h['action'] for h in self.store.history(rid)], ['due', 'quiet_deferred', 'create'])

    def test_restart_after_sleep_does_not_replay_quiet_occurrence(self):
        self.store.set_quiet_hours(True, now=0)
        rid = self.store.create('Stretch', 45, now=india(21, 30))['id']
        restarted = LocalReminders(self.path)
        self.assertEqual(restarted.due(now=india(9, day=22)), [])
        self.assertEqual(restarted.get(rid)['next_due'], india(9, 45, day=22))

    def test_pause_resume_and_ack_history_are_recorded_once(self):
        rid = self.store.create_water(1, now=0)['id']
        self.store.due(now=60)
        self.store.ack(rid, 'snooze', now=61)
        self.store.due(now=361)
        self.store.ack(rid, 'skip', now=362)
        self.store.set_enabled(rid, False, now=363)
        self.store.set_enabled(rid, False, now=364)
        self.store.set_enabled(rid, True, now=365)
        actions = [h['action'] for h in self.store.history(rid)]
        self.assertEqual(actions, ['resume', 'pause', 'skip', 'due', 'snooze', 'due', 'create'])

    def test_invalid_data_does_not_mutate_store(self):
        for title in ['', ' ', 'a' * 161, None]:
            with self.assertRaises(ValueError):
                self.store.create(title)
        for options in [dict(start='24:00'), dict(end='8:00'), dict(end='22:00'),
                        dict(timezone='Definitely/NotReal'), dict(enabled='yes')]:
            with self.assertRaises(ValueError):
                self.store.set_quiet_hours(**{'enabled': True, **options})
        self.assertFalse(self.store.quiet_hours()['enabled'])
        self.assertEqual(self.store.history(), [])
        for limit in [0, 201, True, 1.2]:
            with self.assertRaises(ValueError):
                self.store.history(limit=limit)


if __name__ == '__main__':
    unittest.main()
