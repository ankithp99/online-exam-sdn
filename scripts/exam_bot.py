#!/usr/bin/env python3
"""Automated exam clients for latency, fairness and load tests.

Each bot registers, answers all questions at once and records the server's
response time per answer (answer sent -> "answer_received"). One CSV row is
appended per exam session. Run it on a Mininet host, e.g.:

    h2 python3 scripts/exam_bot.py --clients 5 --label h2
"""

import argparse
import csv
import json
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ANSWERS = ["B", "C", "A", "B", "D"]  # correct answers for app/server.py
FIELDS = ["timestamp_utc", "label", "client", "round", "status",
          "score", "mean_ms", "max_ms", "total_s"]
_csv_lock = threading.Lock()


class LineReader:
    """Read newline-delimited JSON messages from a socket."""

    def __init__(self, sock):
        self.sock, self.buf = sock, bytearray()

    def read(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                return None
            self.buf.extend(chunk)
        line, _, rest = self.buf.partition(b"\n")
        self.buf = bytearray(rest)
        return json.loads(line.decode("utf-8"))


def send(sock, message):
    sock.sendall((json.dumps(message) + "\n").encode("utf-8"))


def run_session(host, port, name, answers=ANSWERS, timeout=10, think=0):
    """Run one exam. Returns a dict with status, score and latencies (ms)."""
    started = time.monotonic()
    out = {"status": "error", "score": "", "latencies": []}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            reader = LineReader(sock)
            reader.read()  # welcome (or "server full" error)
            send(sock, {"type": "register", "name": name})
            message = reader.read()
            if message is None or message.get("type") == "error":
                out["status"] = "rejected"
                return out
            for letter in answers:
                question = reader.read()
                if question is None or question.get("type") != "question":
                    out["status"] = "aborted"
                    return out
                if think:
                    time.sleep(think)  # hold the session open (capacity tests)
                t0 = time.monotonic()
                send(sock, {"type": "answer", "answer": letter})
                ack = reader.read()
                if ack is None or ack.get("type") != "answer_received":
                    out["status"] = "aborted"
                    return out
                out["latencies"].append((time.monotonic() - t0) * 1000)
            result = reader.read()
            if result and result.get("type") == "result":
                out["status"], out["score"] = "ok", result.get("score", "")
    except (OSError, ValueError) as exc:
        out["status"] = f"error: {exc.__class__.__name__}"
    finally:
        out["total_s"] = time.monotonic() - started
    return out


def log_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _csv_lock:
        new = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)


def client_loop(args, index):
    for rnd in range(1, args.repeat + 1):
        result = run_session(args.host, args.port,
                             f"{args.label}-bot{index}", think=args.think)
        lat = result["latencies"]
        log_row(args.csv, {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "label": args.label, "client": index, "round": rnd,
            "status": result["status"], "score": result["score"],
            "mean_ms": round(sum(lat) / len(lat), 3) if lat else "",
            "max_ms": round(max(lat), 3) if lat else "",
            "total_s": round(result.get("total_s", 0), 3),
        })
        print(f"{args.label} bot{index} round {rnd}: {result['status']} "
              f"score={result['score']}", flush=True)
        if rnd < args.repeat:
            time.sleep(args.gap)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="10.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--clients", type=int, default=1, help="parallel bots")
    p.add_argument("--repeat", type=int, default=1, help="exams per bot")
    p.add_argument("--gap", type=float, default=0, help="seconds between exams")
    p.add_argument("--think", type=float, default=0,
                   help="seconds to wait before each answer (holds slots)")
    p.add_argument("--label", default="bot", help="tag, e.g. h2 or static")
    p.add_argument("--csv", default="results/bot_trials.csv")
    args = p.parse_args()
    threads = [threading.Thread(target=client_loop, args=(args, i + 1))
               for i in range(args.clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"Rows appended to {args.csv}")


if __name__ == "__main__":
    main()
