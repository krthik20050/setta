import unittest
from src.desktop_walk import next_position, roam_position, QuietWalk


class DesktopWalkTests(unittest.TestCase):
    def test_quiet_mode_pauses_moves_horizontally_and_never_bounces(self):
        walker = QuietWalk(500, (0, 0, 1536, 816), 144, 160, 0)
        positions, phases = [], set()
        for i in range(1200):
            x, y, phase, _ = walker.step(i / 30)
            self.assertEqual(y, 656)
            self.assertTrue(12 <= x <= 1380)
            positions.append(x)
            phases.add(phase)
        self.assertEqual(phases, {'idle', 'walk'})
        self.assertEqual(positions[0], positions[60])
        self.assertGreater(len(set(positions)), 100)
        self.assertTrue(all(abs(a-b) <= 1 for a,b in zip(positions, positions[1:])))

    def test_roaming_moves_both_axes_and_stays_visible(self):
        x, y, dx, dy = 400, 400, -1, -1
        xs, ys = set(), set()
        for _ in range(4000):
            x, y, dx, dy = roam_position(x, y, dx, dy, (0, 0, 1536, 816))
            xs.add(x)
            ys.add(y)
            self.assertTrue(8 <= x <= 1336)
            self.assertTrue(8 <= y <= 608)
        self.assertGreater(len(xs), 500)
        self.assertGreater(len(ys), 400)

    def test_above_taskbar(self):
        x, y, direction = next_position(400, -1, (0, 0, 1920, 1032))
        self.assertEqual(y + 208, 1032)
        self.assertLess(x, 400)

    def test_turns_at_both_edges(self):
        self.assertEqual(next_position(8, -1, (0, 0, 1920, 1032))[2], 1)
        self.assertEqual(next_position(1720, 1, (0, 0, 1920, 1032))[2], -1)

    def test_secondary_monitor_negative_coordinates(self):
        x, y, _ = next_position(-1000, -1, (-1920, 0, 0, 1040))
        self.assertLess(x, -1000)
        self.assertEqual(y, 832)

    def test_remains_bounded_over_long_walk(self):
        x, direction = 500, -1
        for _ in range(10000):
            x, _, direction = next_position(x, direction, (0, 0, 1920, 1032))
            self.assertTrue(8 <= x <= 1720)
