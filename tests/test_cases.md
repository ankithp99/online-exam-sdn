# Test Cases & Verification Matrix — Online Examination Network

**Project:** Project 18 – Online Examination Network  
**Deliverables:** D1 & D2 Comprehensive Verification Matrix  
**Status:** ALL TESTS VERIFIED & PASSING (100% COMPLETE)  

---

## 1. Test Summary Matrix

| Test ID | Category | Description | Status |
|---|---|---|---|
| **T01** | Mininet Infrastructure | Custom topology creation (h1, h2, h3, s1) on 10.0.0.0/24 subnet | **PASS** |
| **T02** | Layer-2 Reachability | Full mesh host-to-host ping reachability (pingall, 0% packet loss) | **PASS** |
| **T03** | SDN Controller Connect | OpenFlow 1.3 handshake with OS-Ken controller (tcp:127.0.0.1:6653) | **PASS** |
| **T04** | Reactive MAC Learning | Packet-in handling and priority-10 bidirectional forwarding flow installation | **PASS** |
| **T05** | TCP Core Exam Protocol | Multi-threaded TCP socket communication: Welcome, Registration, Question, Answer, Score | **PASS** |
| **T07** | Timed Examination | Server-enforced 120-second countdown deadline timer with auto-submit | **PASS** |
| **T08** | Client Disconnection | Graceful handling of mid-exam student disconnect (Ctrl+C) without socket leak | **PASS** |
| **T09** | Concurrent Students | Simultaneous independent examination sessions on h2 and h3 | **PASS** |
| **T10** | Web UI Integration | REST API health checks (/api/health) and browser-based examination bridge | **PASS** |
| **T12** | Dynamic SDN Detection | Ingress port rate monitoring triggering CONGESTION and priority-20 UDP drop rule | **PASS** |
| **T13** | Dynamic Flow Removal | Automatic deletion of priority-20 drop rule after traffic clears below threshold | **PASS** |
| **T14** | Exam During Congestion | TCP examination completion with zero packet drop while UDP filter is active | **PASS** |
| **T15** | Baseline Response Time | 20-packet ping baseline (0.0% loss) and automated bot latency calibration | **PASS** |
| **T16** | Network Fairness | Dual-stream traffic with Jain Fairness Index computation (Score: 0.9941) | **PASS** |
| **T17** | Traffic Stress Test | 20 Mbps UDP background flooding with TCP exam stream isolation | **PASS** |
| **T18** | Capacity Saturation | 20 concurrent student bots admitted; 21st student rejected with [BUSY] | **PASS** |
| **T19** | Controller Outage | Flow persistence during controller downtime and recovery after restart | **PASS** |
| **T20** | Flow Expiry & Re-learn | 60-second idle timeout eviction of priority-10 flows and dynamic re-learning | **PASS** |
| **T21** | Malformed Input Robust | Server resilience against corrupted JSON, non-existent message types, and bad options | **PASS** |
| **T22** | Automated Unit Tests | 20 automated unit tests executed across protocol, congestion math, and bots | **PASS** |

---

## 2. Detailed Execution Evidence & Observed Results

### T01 – T04: Network Infrastructure & SDN Controller
- **Command:** sudo mn --custom mininet/topology.py --topo onlineexam --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6653 --link tc,bw=10
- **Expected Result:** Switch s1 connects to controller; pingall reports 0% loss; priority-10 flows installed.
- **Observed Result:** Switch s1 connected successfully to controller on port 6653 (is_connected: true). pingall completed with 0% dropped (6/6 received). Controller dynamically installed priority-10 forwarding rules for all host MAC pairs.
- **Status:** **PASS**

### T05 & T09: Concurrent Exam Application
- **Command:** h2 python3 app/client.py & and h3 python3 app/client.py
- **Expected Result:** Independent simultaneous student sessions with isolated countdown timers and scoring.
- **Observed Result:** Both students took the exam concurrently. Server spawned daemon threads per client. Alice completed 5/5 with 80% (4/5) and Bob completed 5/5 with 100% (5/5) without any race conditions.
- **Status:** **PASS**

### T08: Client Disconnection Handling
- **Command:** Terminate client via Ctrl + C during Question 2.
- **Expected Result:** Server catches disconnection and frees worker slot cleanly.
- **Observed Result:** Server caught ConnectionResetError, printed [DISCONNECTED] Student disconnected unexpectedly, cleanly closed the socket, and released the thread semaphore slot without hanging.
- **Status:** **PASS**

### T10: Web UI & REST API Bridge
- **Command:** h2 curl -i http://10.0.0.1:8080/api/health
- **Expected Result:** HTTP 200 OK with health status JSON.
- **Observed Result:** Returned HTTP/1.0 200 OK with {"ok": true, "exam_server": "127.0.0.1:5000"}. Browser interface loaded questions and submitted answers smoothly.
- **Status:** **PASS**

### T12 – T14: Dynamic SDN Congestion Mitigation
- **Command:** h3 iperf3 -c 10.0.0.2 -u -b 1M -t 90 &
- **Expected Result:** Ingress rate exceeds 100 kbps, controller installs priority-20 drop rule, UDP traffic drops.
- **Observed Result:** Controller detected traffic on port 3 at 146,481 bps and logged CONGESTION: UDP filter enabled. Switch s1 installed priority=20,ip,nw_proto=17 actions=drop. Delivered UDP rate dropped from 1,000 Kbps down to 7.85 Kbps (99.2% suppression). Exam on h2 completed with 0% packet loss. When traffic ceased, controller logged CONGESTION CLEARED (rate=67 bps) and deleted the rule.
- **Status:** **PASS**

### T15 & T16: Response Time & Network Fairness
- **Command:** python3 scripts/summarize.py results/fairness.csv --fair
- **Expected Result:** Sub-millisecond latency and balanced resource sharing between candidate hosts.
- **Observed Result:** 50 sessions on h2 averaged 0.17 ms latency; 50 sessions on h3 averaged 0.20 ms latency. Calculated Jain Fairness Index was 0.9941 (near-perfect 1.0 distribution).
- **Status:** **PASS**

### T18: Server Capacity Saturation (20 + 1)
- **Command:** 20 bots launched with 15s think time; 21st bot launched within 5 seconds.
- **Expected Result:** 20 sessions admitted; 21st session rejected with busy response.
- **Observed Result:** Exactly 20 candidate sessions were admitted and completed. Server log explicitly recorded [BUSY] Rejected connection from (10.0.0.2, 43488). The 21st client received the server full notification without crashing the daemon.
- **Status:** **PASS**

### T20: OpenFlow Flow Expiry & Re-learning
- **Command:** Idle for 70 seconds after traffic generation.
- **Expected Result:** Priority-10 flows expire after 60s idle timeout; re-learned upon new packets.
- **Observed Result:** Priority-10 flows expired and vanished from ovs-ofctl dump-flows s1 after 60 seconds. Subsequent pingall re-triggered packet-in events, and controller re-installed forwarding rules.
- **Status:** **PASS**

### T21: Malformed Message Resilience
- **Command:** Transmit raw non-JSON bytes and invalid action payloads to 10.0.0.1:5000.
- **Expected Result:** Server rejects malformed data without crashing.
- **Observed Result:** Server logged INVALID MESSAGE and Valid registration is required, rejected invalid options, and remained fully operational.
- **Status:** **PASS**

### T22: Automated Unit Test Suite
- **Command:** python3 -m unittest discover -s tests -v
- **Expected Result:** All unit tests pass.
- **Observed Result:** All 20 automated tests ran and passed in 1.215s with status OK.
- **Status:** **PASS**


