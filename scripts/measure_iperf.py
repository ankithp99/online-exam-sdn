#!/usr/bin/env python3
"""Run repeatable iperf3 client trials and append one row per trial to CSV."""

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_trial(server, mode, protocol, duration, bandwidth, trial):
    command = ["iperf3", "-c", server, "-J", "-t", str(duration)]
    command += ["-u", "-b", bandwidth] if protocol == "udp" else []
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        detail = completed.stderr.strip()
        if not detail and completed.stdout.strip():
            try:
                error_report = json.loads(completed.stdout)
                detail = error_report.get("error", "")
            except json.JSONDecodeError:
                detail = completed.stdout.strip()
        detail = detail or "iperf3 returned no error text on stdout or stderr"
        raise RuntimeError(
            f"iperf3 trial {trial} failed (exit {completed.returncode}): {detail}"
        )

    try:
        report = json.loads(completed.stdout)
        end = report["end"]
        summary = end.get("sum_received") or end["sum"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Could not parse iperf3 JSON for trial {trial}: {exc}") from exc

    udp = end.get("sum") or {}
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "protocol": protocol,
        "trial": trial,
        "duration_s": duration,
        "offered_bandwidth": bandwidth if protocol == "udp" else "",
        "throughput_mbps": round(summary.get("bits_per_second", 0) / 1_000_000, 6),
        "retransmits": summary.get("retransmits", ""),
        "udp_lost_percent": udp.get("lost_percent", "") if protocol == "udp" else "",
    }


def append_rows(csv_path, rows):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    exists = csv_path.exists() and csv_path.stat().st_size > 0
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", help="iperf3 server IPv4 address")
    parser.add_argument("--mode", choices=("static", "dynamic"), required=True)
    parser.add_argument("--protocol", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--bandwidth", default="1M", help="UDP offered rate")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--csv", type=Path, default=Path("results/iperf_trials.csv"))
    args = parser.parse_args()
    if args.duration <= 0 or args.trials <= 0:
        parser.error("duration and trials must be positive")

    completed_trials = 0
    try:
        for trial in range(1, args.trials + 1):
            row = run_trial(
                args.server, args.mode, args.protocol, args.duration,
                args.bandwidth, trial,
            )
            append_rows(args.csv, [row])
            completed_trials += 1
            print(
                "{mode} {protocol} trial {trial}: {throughput_mbps} Mbps".format(**row),
                flush=True,
            )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Appended {completed_trials} trials to {args.csv}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
