# Online Examination Network Using SDN

## 1. Project Overview

The **Online Examination Network** is a client-server application that allows multiple students to take an online multiple-choice examination over a Software-Defined Networking (SDN) network.

The application uses TCP socket programming for communication between student clients and the examination server. Mininet is used to create a virtual network topology, Open vSwitch acts as the software switch, and an OS-Ken SDN controller manages network forwarding behavior.

The project demonstrates socket programming, concurrent client handling, virtual network emulation, SDN-based packet forwarding, examination time limits, and basic protocol testing.

## 2. Objectives

- Implement client-server communication using TCP sockets.
- Support multiple student clients connecting to the examination server.
- Exchange registration, question, answer, and result messages using JSON.
- Create a virtual network using Mininet and Open vSwitch.
- Connect the switch to an SDN controller using OpenFlow 1.3.
- Implement MAC address learning and forwarding in the SDN controller.
- Enforce a time limit for the examination.
- Test the application protocol and document the execution procedure.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | Application and controller implementation |
| TCP sockets | Reliable communication between clients and server |
| JSON | Message exchange format |
| Multithreading | Handling multiple student connections |
| Mininet | Virtual network emulation |
| Open vSwitch | Software-based network switching |
| OpenFlow 1.3 | Communication between switch and controller |
| OS-Ken | SDN controller framework |
| Linux / Ubuntu | Development and execution environment |
| Python unittest | Basic automated tests |

## 4. System Architecture

The network consists of one examination server, two student hosts, one Open vSwitch, and an SDN controller.

```text
                 SDN Controller
                    (OS-Ken)
                       |
                 OpenFlow 1.3
                       |
                  Open vSwitch
                     (s1)
                   /  |  \
                  /   |   \
                 /    |    \
           Server   Student 1   Student 2
             h1         h2          h3
        10.0.0.1    10.0.0.2   10.0.0.3
```

### Components

- **Examination server (h1):** Hosts the examination, sends questions, receives student answers, tracks scores, and returns results.
- **Student clients (h2 and h3):** Connect to the server, register with a student name, answer questions, and receive their results.
- **Open vSwitch (s1):** Forwards traffic between hosts in the virtual network.
- **OS-Ken controller:** Learns MAC addresses and manages forwarding rules through OpenFlow 1.3.
- **Mininet:** Creates and runs the virtual hosts, links, and switch.

## 5. Project Structure

```text
online-exam-sdn/
├── app/
│   ├── client.py
│   └── server.py
├── docs/
│   └── README.md
├── mininet/
│   └── topology.py
├── sdn/
│   ├── requirements.txt
│   └── ryu_controller.py
└── tests/
    └── test_server.py
```

## 6. Application Workflow

1. The examination server starts and listens for incoming TCP connections on port `5000`.
2. A student client connects to the server.
3. The client sends a registration message containing the student's name.
4. The server starts the examination timer and sends the questions.
5. The client submits answers using JSON messages.
6. The server evaluates the answers and calculates the score.
7. The server sends the final examination result to the client.
8. The server closes the connection when the session ends.

The server uses a separate thread for each connected client so that multiple students can take the examination concurrently.

## 7. Installation and Requirements

The project is intended to run on Ubuntu Linux.

Install the required system packages:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv mininet openvswitch-switch git
```

Install OS-Ken in a Python virtual environment:

```bash
cd ~/online-exam-sdn
python3 -m venv .venv-osken31
source .venv-osken31/bin/activate
pip install -r sdn/requirements.txt
```

If the virtual environment has already been created and the dependencies installed, activate it instead of creating it again.

## 8. Running the Project

The controller and Mininet should run in separate terminal sessions.

### Step 1: Start the SDN controller

Open the first terminal:

```bash
cd ~/online-exam-sdn
source .venv-osken31/bin/activate
osken-manager --ofp-tcp-listen-port 6653 sdn/ryu_controller.py
```

Keep this terminal open while running the network.

### Step 2: Start the Mininet topology

Open a second terminal:

```bash
cd ~/online-exam-sdn
sudo mn --custom "$(pwd)/mininet/topology.py" --topo onlineexam --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6653
```

This starts the virtual network and connects the switch to the controller.

### Step 3: Verify connectivity

At the Mininet prompt, run:

```text
pingall
```

Successful connectivity should report:

```text
0% dropped
```

The exact output may vary, but all three hosts should be able to reach one another.

### Step 4: Start the examination server

At the Mininet prompt:

```text
h1 python3 app/server.py &
```

The server listens on `10.0.0.1:5000`.

### Step 5: Start a student client

At the Mininet prompt:

```text
h2 python3 app/client.py
```

Enter a student name and answer the examination questions.

### Step 6: Test a second student

Open another terminal and enter the Mininet CLI using the same topology and controller configuration, or use a second client from the existing Mininet session if supported by your setup.

For example, from the existing Mininet prompt, run:

```text
h3 python3 app/client.py
```

Both clients should be able to connect to the server and take the examination.

**Important:** When running clients inside Mininet, the client host setting must be `10.0.0.1`, not `127.0.0.1`. The loopback address refers to the client host itself.

## 9. Testing

### 9.1 Python syntax checks

From the project directory, run:

```bash
python3 -m py_compile app/server.py app/client.py sdn/ryu_controller.py mininet/topology.py
```

No output indicates that Python did not report syntax errors in these files.

### 9.2 Automated protocol tests

Run:

```bash
python3 -m unittest discover -s tests -v
```

The basic tests check JSON registration and answer message formats. These tests do not replace integration tests against a running server.

### 9.3 Network connectivity test

At the Mininet prompt:

```text
pingall
```

Verify that all hosts can communicate.

### 9.4 Controller connection test

From a separate Ubuntu terminal:

```bash
sudo ovs-vsctl show
```

Verify that the switch has a controller connection and that `is_connected` is `true`.

Check the switch protocol:

```bash
sudo ovs-vsctl get bridge s1 protocols
```

Expected output includes:

```text
[OpenFlow13]
```

### 9.5 Examination integration test

1. Start the controller and Mininet.
2. Start the server on `h1`.
3. Connect a student client from `h2`.
4. Register and answer the questions.
5. Confirm that the server returns a final score.
6. Connect a second student from `h3`.
7. Test how the application handles disconnections and the examination deadline.

Record the actual results observed during testing rather than assuming that every scenario has passed.

## 10. SDN Controller Behavior

The SDN controller is designed to use MAC address learning to forward packets.

Its main responsibilities include:

- Receiving packet-in events from the switch.
- Learning the source MAC address and associated switch port.
- Forwarding packets to a known destination port.
- Flooding packets when the destination MAC address is unknown.
- Installing OpenFlow forwarding rules to reduce the need for repeated controller processing.

If the optional congestion-monitoring code is installed, its port-statistics and UDP-filtering behavior should also be tested separately. Do not describe congestion handling as verified until the controller logs, traffic behavior, and flow rules have been checked.

## 11. Network Configuration

| Host | IP address | Role |
|---|---|---|
| h1 | `10.0.0.1/24` | Examination server |
| h2 | `10.0.0.2/24` | Student client 1 |
| h3 | `10.0.0.3/24` | Student client 2 |
| s1 | OpenFlow 1.3 | Software switch |
| OS-Ken | `127.0.0.1:6653` | SDN controller endpoint |

The application server listens on TCP port `5000`. The switch connects to the controller on port `6653`.

## 12. Limitations

- The current topology uses a single switch and does not provide an alternate network path.
- Link-failure recovery through rerouting is not demonstrated by this topology.
- The basic automated tests validate message formats rather than every end-to-end application scenario.
- Congestion detection and traffic filtering require separate traffic-generation and flow-rule verification.
- The examination application is a demonstration project and is not intended to provide production-grade authentication, encrypted communication, or tamper-resistant examination security.

## 13. Future Enhancements

- Add more student hosts and support larger examinations.
- Introduce multiple switches and redundant links.
- Implement path selection and rerouting after link failures.
- Improve congestion detection and evaluate network performance under load.
- Add secure student authentication and encrypted connections.
- Store examination results in a database.
- Add more automated integration tests.
- Measure latency, throughput, packet loss, and controller response time.

## 14. Conclusion

The Online Examination Network combines TCP socket programming with SDN-based network emulation. The application demonstrates communication between multiple student clients and an examination server, while Mininet, Open vSwitch, OpenFlow 1.3, and OS-Ken provide the network infrastructure and programmable forwarding behavior.

The project provides a foundation for exploring distributed applications, network control, and automated network testing.

## 15. Repository

**Project:** Project 18 – Online Examination Network

**Repository:** https://github.com/ankithp99/online-exam-sdn.git



## 16. D2 Completion Scenarios: Application and Dynamic SDN

The server supports up to 20 simultaneous exam sessions. Each student is handled in its own thread; if all slots are occupied, the server returns a clear busy response instead of creating unbounded worker threads. Sessions include registration timeout, exam deadline, answer validation, scoring, and a final result message.

### 16.1 Verify complete application functionality

1. Start the controller, Mininet, and exam server using Sections 8 and 9.
2. From the Mininet prompt, start one client on each student host:

   ```text
   h2 python3 app/client.py
   h3 python3 app/client.py
   ```

3. Register different student names, answer the questions, and confirm each client receives its own score and result.
4. Repeat with one client disconnected during the exam and one client that does not register within 60 seconds. Confirm the other session continues and the server logs the disconnect or registration timeout.
5. For the capacity response, temporarily set `MAX_CONCURRENT_CLIENTS` to `1`, restart the server, start one exam session, then connect a second client. Confirm the second client receives the busy message. Restore the setting to `20` after this check.

Record observed results and environment details in the final demo notes. The source code alone does not establish that a scenario was successfully run.

### 16.2 Demonstrate dynamic congestion filtering while the exam runs

The controller samples OpenFlow port counters every five seconds. When traffic on a switch port reaches `CONGESTION_THRESHOLD_BPS` (default `100000` bits/s), it installs a higher-priority rule that drops UDP arriving on that port. The exam uses TCP on port `5000`, so its TCP flows remain eligible for normal forwarding while the selected UDP load is filtered. When measured traffic falls below `CLEAR_THRESHOLD_BPS` (default `50000` bits/s), the controller removes that temporary rule.

1. At the Mininet prompt, start a UDP receiver on `h2` and launch a 30-second UDP load from `h3` in the background:

   ```text
   h2 iperf3 -s > /tmp/iperf-server.log 2>&1 &
   h3 iperf3 -c 10.0.0.2 -u -b 1M -t 30 &
   ```

2. While the load is active, start the exam client on `h2` and complete an exam:

   ```text
   h2 python3 app/client.py
   ```

3. Check the controller log for `CONGESTION` and confirm the temporary UDP drop rule with:

   ```bash
   sudo ovs-ofctl -O OpenFlow13 dump-flows s1
   ```

   The matching rule should show `udp` and the ingress port for `h3`. Confirm that the exam client still completes over TCP while UDP traffic is filtered.

4. Stop the UDP generator and wait for the controller to observe a rate below the clear threshold. Confirm the `CONGESTION CLEARED` log and that the UDP rule is gone from the flow table.
5. Save controller logs, flow-table output, and the exam result as demo evidence. If `iperf3` is not installed, install it on the Ubuntu host before the demonstration.

These steps describe the expected demonstration. Do not report the dynamic scenario or concurrent exam as verified until the results have actually been observed in Mininet.
