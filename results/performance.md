# D1 Test Results — Online Examination Network

## 1. Mininet Connectivity
- Topology: h1, h2, h3 connected through switch s1.
- Test: pingall
- Result: 6/6 host-to-host ping checks received.
- Packet loss: 0%.

## 2. Online Examination Application
- TCP client-server exam tested.
- Exam result displayed successfully.
- One observed run: 2/5 (40%).
- Another observed run: 4/5 (80%).

## 3. OpenFlow
- Open vSwitch: 3.7.1.
- OpenFlow version used for flow inspection: OpenFlow 1.3.
- Controller connection: tcp:127.0.0.1:6653.
- A priority-100 NORMAL forwarding rule was added manually.
- Dynamic forwarding-rule installation by the controller remains unverified.

## 4. Limitations
- Controller-driven forwarding must be verified separately.
- Results represent observed test runs, not a comprehensive performance evaluation.
