import pathlib
import socket
import sys
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

import exam_bot  # noqa: E402
import server  # noqa: E402
import summarize  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class StatsTests(unittest.TestCase):
    def test_jain_equal_values_is_one(self):
        self.assertAlmostEqual(summarize.jain_index([5, 5, 5]), 1.0)

    def test_jain_unequal_values_is_lower(self):
        self.assertAlmostEqual(summarize.jain_index([10, 0.0001]), 0.5, places=3)

    def test_percentile(self):
        self.assertEqual(summarize.percentile([1, 2, 3, 4, 5], 100), 5)
        self.assertEqual(summarize.percentile([1, 2, 3, 4, 5], 0), 1)


class LiveServerTests(unittest.TestCase):
    """Run the real server on a loopback port and drive it with the bot."""

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        server.HOST, server.PORT = "127.0.0.1", cls.port
        server.CLIENT_SLOTS = threading.BoundedSemaphore(1)
        threading.Thread(target=server.start_server, daemon=True).start()
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        time.sleep(0.5)

    def test_full_exam_scores_five(self):
        result = exam_bot.run_session("127.0.0.1", self.port, "t-ok")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["score"], 5)
        self.assertEqual(len(result["latencies"]), 5)

    def test_second_client_rejected_when_server_full(self):
        time.sleep(0.5)  # let any previous session release its slot
        holder = socket.create_connection(("127.0.0.1", self.port), 5)
        reader = exam_bot.LineReader(holder)
        reader.read()
        exam_bot.send(holder, {"type": "register", "name": "holder"})
        reader.read()  # exam_started: the only slot is now occupied
        try:
            result = exam_bot.run_session("127.0.0.1", self.port, "t-full")
            self.assertEqual(result["status"], "rejected")
        finally:
            holder.close()


if __name__ == "__main__":
    unittest.main()
