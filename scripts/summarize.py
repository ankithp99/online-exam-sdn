#!/usr/bin/env python3
"""Summarise bot CSV results and compute Jain's fairness index.

    python3 scripts/summarize.py results/bot_trials.csv
    python3 scripts/summarize.py --jain 4.7 4.9      # raw throughputs
"""

import argparse
import csv
from collections import defaultdict


def jain_index(values):
    """Jain's index (sum x)^2 / (n * sum x^2): 1.0 = perfectly fair."""
    values = [float(v) for v in values]
    if not values or not any(values):
        raise ValueError("need at least one non-zero value")
    return sum(values) ** 2 / (len(values) * sum(v * v for v in values))


def percentile(values, pct):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("no values")
    rank = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[rank]


def summarise(rows):
    """Return {label: stats} for rows with status ok."""
    groups = defaultdict(list)
    for row in rows:
        if row["status"] == "ok" and row["mean_ms"] != "":
            groups[row["label"]].append(row)
    result = {}
    for label, items in groups.items():
        means = [float(r["mean_ms"]) for r in items]
        result[label] = {
            "sessions": len(items),
            "mean_ms": sum(means) / len(means),
            "p95_ms": percentile(means, 95),
            "max_ms": max(float(r["max_ms"]) for r in items),
        }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", nargs="?")
    p.add_argument("--jain", nargs="+", type=float, help="raw allocations")
    p.add_argument("--fair", action="store_true",
                   help="also print Jain index across labels (1/mean latency)")
    args = p.parse_args()
    if args.jain:
        print(f"Jain index: {jain_index(args.jain):.4f}")
        return
    if not args.csv:
        p.error("give a CSV file or --jain values")
    with open(args.csv, newline="", encoding="utf-8") as handle:
        stats = summarise(list(csv.DictReader(handle)))
    print(f"{'label':<12}{'sessions':>9}{'mean ms':>10}{'p95 ms':>10}{'max ms':>10}")
    for label, s in sorted(stats.items()):
        print(f"{label:<12}{s['sessions']:>9}{s['mean_ms']:>10.2f}"
              f"{s['p95_ms']:>10.2f}{s['max_ms']:>10.2f}")
    if args.fair and len(stats) > 1:
        # Fairness across labels using 1/latency as the "service" each gets.
        index = jain_index([1 / s["mean_ms"] for s in stats.values()])
        print(f"Jain index across labels (1/mean latency): {index:.4f}")


if __name__ == "__main__":
    main()
