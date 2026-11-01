import csv
import json
import pathlib
import sys
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import measure_iperf


class IperfMeasurementTests(unittest.TestCase):
    def test_tcp_trial_builds_command_and_parses_received_throughput(self):
        report = {
            "end": {
                "sum_received": {"bits_per_second": 2_500_000, "retransmits": 4},
                "sum": {"bits_per_second": 2_400_000},
            }
        }
        with patch.object(
            measure_iperf.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr=""),
        ) as run:
            row = measure_iperf.run_trial("10.0.0.2", "dynamic", "tcp", 20, "1M", 1)

        self.assertEqual(run.call_args.args[0], [
            "iperf3", "-c", "10.0.0.2", "-J", "-t", "20",
        ])
        self.assertEqual(row["throughput_mbps"], 2.5)
        self.assertEqual(row["retransmits"], 4)
        self.assertEqual(row["udp_lost_percent"], "")

    def test_udp_trial_includes_bandwidth_and_loss(self):
        report = {
            "end": {
                "sum_received": {"bits_per_second": 500_000},
                "sum": {"bits_per_second": 900_000, "lost_percent": 12.5},
            }
        }
        with patch.object(
            measure_iperf.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr=""),
        ) as run:
            row = measure_iperf.run_trial("10.0.0.2", "dynamic", "udp", 20, "1M", 2)

        self.assertEqual(run.call_args.args[0], [
            "iperf3", "-c", "10.0.0.2", "-J", "-t", "20", "-u", "-b", "1M",
        ])
        self.assertEqual(row["throughput_mbps"], 0.5)
        self.assertEqual(row["offered_bandwidth"], "1M")
        self.assertEqual(row["udp_lost_percent"], 12.5)

    def test_csv_is_created_with_header_and_appended_rows(self):
        row = {
            "timestamp_utc": "2026-11-01T00:00:00+00:00",
            "mode": "static", "protocol": "tcp", "trial": 1,
            "duration_s": 3, "offered_bandwidth": "",
            "throughput_mbps": 1.25, "retransmits": 0,
            "udp_lost_percent": "",
        }
        with tempfile.TemporaryDirectory(
            dir=pathlib.Path(__file__).resolve().parent
        ) as directory:
            path = pathlib.Path(directory) / "results" / "trials.csv"
            measure_iperf.append_rows(path, [row])
            measure_iperf.append_rows(path, [{**row, "trial": 2}])
            with path.open(newline="", encoding="utf-8") as handle:
                records = list(csv.DictReader(handle))

        self.assertEqual(len(records), 2)
        self.assertEqual([record["trial"] for record in records], ["1", "2"])

    def test_nonzero_iperf_exit_reports_error_even_without_stderr(self):
        with patch.object(
            measure_iperf.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=1, stdout="", stderr=""),
        ):
            with self.assertRaisesRegex(RuntimeError, "returned no error text"):
                measure_iperf.run_trial("10.0.0.2", "dynamic", "udp", 20, "1M", 1)

    def test_nonzero_json_error_is_reported_from_stdout(self):
        with patch.object(
            measure_iperf.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=1,
                stdout=json.dumps({"error": "server rejected test"}),
                stderr="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "server rejected test"):
                measure_iperf.run_trial("10.0.0.2", "dynamic", "udp", 20, "1M", 1)

    def test_invalid_json_is_reported(self):
        with patch.object(
            measure_iperf.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="not json", stderr=""),
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not parse iperf3 JSON"):
                measure_iperf.run_trial("10.0.0.2", "dynamic", "tcp", 20, "1M", 1)

    def test_successful_trial_is_saved_before_a_later_trial_fails(self):
        row = {
            "timestamp_utc": "2026-11-01T00:00:00+00:00",
            "mode": "dynamic", "protocol": "udp", "trial": 1,
            "duration_s": 3, "offered_bandwidth": "1M",
            "throughput_mbps": 0.5, "retransmits": "",
            "udp_lost_percent": 12.5,
        }
        with tempfile.TemporaryDirectory(
            dir=pathlib.Path(__file__).resolve().parent
        ) as directory:
            output = pathlib.Path(directory) / "partial.csv"
            with patch.object(sys, "argv", [
                "measure_iperf.py", "10.0.0.2", "--mode", "dynamic",
                "--protocol", "udp", "--duration", "3", "--trials", "3",
                "--csv", str(output),
            ]), patch.object(
                measure_iperf, "run_trial", side_effect=[row, RuntimeError("trial 2 failed")]
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = measure_iperf.main()

            with output.open(newline="", encoding="utf-8") as handle:
                records = list(csv.DictReader(handle))

        self.assertEqual(result, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["trial"], "1")


if __name__ == "__main__":
    unittest.main()
