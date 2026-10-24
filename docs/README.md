# Online Examination Network using Mininet and SDN

## Project Overview
A networked examination application using TCP sockets, a Python client-server architecture, and Mininet.

## Features
- TCP client-server communication
- Multiple student clients
- Exam questions and answer submission
- Timer-based examination
- Automatic scoring and percentage calculation
- Mininet topology with one server, two student hosts, and one switch
- Open vSwitch forwarding rules
- Ryu SDN controller source included; controller integration requires runtime verification

## Topology
- h1: Exam server — 10.0.0.1
- h2: Student 1 — 10.0.0.2
- h3: Student 2 — 10.0.0.3
- s1: Open vSwitch

## Run the Application
1. Start the Mininet topology.
2. Configure switch forwarding or connect a compatible SDN controller.
3. Start the exam server on h1.
4. Run the client on h2 or h3.
5. Complete the exam and record the score.

## Testing
- Mininet connectivity tested successfully: 6/6 hosts' ping checks received.
- Student exam execution tested through Mininet.
- One observed student result: 4/5 (80%).
- Ryu runtime integration remains to be verified.

## Project Limitations
Controller source code alone does not establish a working SDN controller. Runtime controller connection and flow installation must be demonstrated separately.
