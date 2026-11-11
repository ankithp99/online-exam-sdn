# Performance Results — Online Examination Network

Emulated network (Mininet); values are virtual-link measurements, not physical capacity.
Setup for bandwidth-limited runs: `sudo mn ... --link tc,bw=10` (10 Mbit/s per link).
Static = controller started with `CONGESTION_THRESHOLD_BPS=999999999 CLEAR_THRESHOLD_BPS=1`
(filter never triggers). Dynamic = default thresholds (100 kbit/s / 50 kbit/s, 5 s poll).

## 1. Baseline (unshaped links)
| Test | Result |
|---|---|
| TCP iperf h2 → h1, 5 s | 59.3 Gbits/s |
| pingall | 0% dropped (6/6) |

## 2. TCP throughput, no UDP load (3 trials, Mbit/s)
| Mode | T1 | T2 | T3 | Mean |
|---|---|---|---|---|
| Static | | | | |
| Dynamic | | | | |

## 3. UDP 1 Mbit/s h3 → h2, 90 s (delivered rate from iperf3 server log)
| Mode | Delivered (Mbit/s) | Loss % | Filter triggered after (s) |
|---|---|---|---|
| Static | | | n/a |
| Dynamic | | | |

## 4. Exam response time under UDP flood (h3 → h1 at 20 Mbit/s, 10 Mbit/s links)
| Mode | Idle ping avg (ms) | Flood ping avg (ms) | Bot mean (ms) | Bot p95 (ms) | Exams completed |
|---|---|---|---|---|---|
| Static | | | | | |
| Dynamic | | | | | |

## 5. Fairness (Jain's index, 1.0 = perfectly fair)
| Scenario | h2 | h3 | Jain index |
|---|---|---|---|
| 2 iperf3 TCP flows to h1 (Mbit/s) | | | |
| 5 bots per host, mean latency (ms) | | | |

## 6. Capacity
| Clients | Completed | Rejected |
|---|---|---|
| 20 | | |
| 21 | | |

Raw data: `iperf_trials.csv`, `bot_trials.csv`. Summary: `python3 scripts/summarize.py results/bot_trials.csv`.
