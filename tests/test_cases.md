# Test Cases — Online Examination Network

Environment: Ubuntu (VirtualBox), Mininet 2.3.0, Open vSwitch 3.7.1, OS-Ken 3.0.1, Python 3.14, iperf3.
Status key: PASS = observed and evidenced · TODO = fill in after running (see Section 2).

## 1. Completed tests (D1 and D2)

| ID | Test | Command / action | Expected | Observed | Status |
|---|---|---|---|---|---|
| T01 | Mininet setup | `sudo mn --custom mininet/topology.py --topo onlineexam --controller=remote` | h1, h2, h3, s1 created | All created | PASS |
| T02 | Connectivity | `pingall` | 0% dropped | 6/6 received | PASS |
| T03 | Controller link | `sh ovs-vsctl show` | `is_connected: true` | true, tcp:127.0.0.1:6653 | PASS |
| T04 | MAC learning / flows | `sh ovs-ofctl -O OpenFlow13 dump-flows s1` | priority-10 entries | Learned entries visible | PASS |
| T05 | TCP exam session | `h1 python3 app/server.py &`, `h2 python3 app/client.py` | Questions, answers, result | Result returned | PASS |
| T06 | TCP throughput | `h2 iperf -c 10.0.0.1 -t 5` | Transfer completes | 59.3 Gbits/s (emulator figure, not physical capacity) | PASS |
| T07 | Concurrent students | Clients on h2 and h3 | Independent results | Prasanth 3/5 (60%); Ankith 4/5 (80%) | PASS |
| T08 | Disconnect | Client closed mid-exam | Other session unaffected | Prasanth disconnected; Ankith finished 4/5 | PASS |
| T09 | Registration timeout | Connect, do not register | Timeout logged after 60 s | `[TIMEOUT]` in server log | PASS |
| T10 | Capacity limit | `MAX_CONCURRENT_CLIENTS=1`, two clients | Second gets "server is full" | h2 admitted, h3 rejected | PASS |
| T11 | Unit + integration tests | `python3 -m unittest discover -s tests -v` | All pass | 20 tests OK (incl. live-server bot tests) | PASS |

## 2. Tests to run and record (D2 dynamic SDN, robustness, performance)

| ID | Test | Command / action | Expected | Observed | Status |
|---|---|---|---|---|---|
| T12 | UDP filter installed mid-load | `h3 iperf3 -c 10.0.0.2 -u -b 1M -t 90 &`; at ~15 s `sh ovs-ofctl -O OpenFlow13 dump-flows s1` | priority=20, `udp`, `in_port=s1-eth3`, drop; `CONGESTION` in controller log | | TODO |
| T13 | Filter cleared | Wait ~10 s after load ends; dump flows | `CONGESTION CLEARED`; rule gone | | TODO |
| T14 | Exam during congestion | `h2 python3 app/client.py` while T12 runs | Exam completes over TCP | | TODO |
| T15 | Idle baseline | `h2 ping -c 20 10.0.0.1`; `exam_bot.py --label idle` | RTT and per-answer latency baseline | | TODO |
| T16 | Fairness | 5 bots on h2 + 5 on h3; two simultaneous iperf3 TCP flows; `summarize.py` | Jain index near 1.0 | | TODO |
| T17 | Static vs dynamic under flood | h3→h1 UDP 20 Mbit/s on 10 Mbit/s links; ping + bots on h2, once per mode | Dynamic recovers after filter; static stays degraded | | TODO |
| T18 | Concurrency + capacity | 20 bots, then a 21st (MAX=20) | 20 complete; 21st rejected | | TODO |
| T19 | Controller outage | Stop OS-Ken mid-exam, restart | Installed flows keep forwarding; relearn after restart | | TODO |
| T20 | Flow expiry | Idle >60 s then `pingall` | New packet-in, flows relearned | | TODO |
| T21 | Malformed input | `h2 nc 10.0.0.1 5000`: bad JSON, wrong type, invalid letter; no answers until 120 s | Server survives; partial result | | TODO |
| T22 | Clean-clone reproduction | Fresh clone, follow `docs/README.md` only | Works as written | | TODO |
