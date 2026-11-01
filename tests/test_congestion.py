import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "sdn"))
from congestion import congestion_transition, counter_rate_bps


class PortCongestionTests(unittest.TestCase):
    def test_rate_uses_counter_delta_and_elapsed_time(self):
        self.assertEqual(counter_rate_bps(100, 2.0, 1100, 3.0), 8000)

    def test_counter_reset_and_nonpositive_elapsed_are_ignored(self):
        self.assertIsNone(counter_rate_bps(100, 2.0, 50, 3.0))
        self.assertIsNone(counter_rate_bps(100, 2.0, 200, 2.0))

    def test_threshold_hysteresis_prevents_flapping(self):
        self.assertEqual(congestion_transition(False, 100, 100, 50), "congested")
        self.assertIsNone(congestion_transition(True, 75, 100, 50))
        self.assertEqual(congestion_transition(True, 49, 100, 50), "clear")
        self.assertIsNone(congestion_transition(False, 75, 100, 50))

    def test_threshold_order_is_validated(self):
        with self.assertRaises(ValueError):
            congestion_transition(False, 1, 10, 20)


if __name__ == "__main__":
    unittest.main()
