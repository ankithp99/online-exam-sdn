D1 Test Cases – Online Examination Network
1. Mininet Setup

    Test: Started the Mininet topology.
    Expected: Three hosts (h1, h2, h3) and one switch (s1) should start.
    Result: All three hosts and the switch were created successfully.
    Status: PASS

2. Checking Network Connectivity

    Test: Ran pingall to check whether the hosts could communicate.
    Expected: All hosts should be able to reach each other.
    Result: All 6 ping checks were successful with 0% packet loss.
    Status: PASS

3. TCP Server and Client

    Test: Checked the connection between the exam server and student client.
    Expected: The client should connect to the server and receive the exam questions.
    Result: Needs to be tested again and confirmed.
    Status: PENDING

4. Exam and Result

    Test: Attempted the exam and submitted the answers.
    Expected: The server should calculate the score and return the result.
    Result: One test run returned a score of 4 out of 5 (80%).
    Status: PASS

5. SDN Controller Connection

    Test: Checked whether the Open vSwitch was connected to the controller.
    Expected: The switch should show an active controller connection.
    Result: The output showed is_connected: true.
    Status: PASS

6. SDN Forwarding

    Test: Checked whether the controller was handling packets and controlling forwarding.
    Expected: Packets should be forwarded through the controller’s logic.
    Result: Still needs to be verified.
    Status: PENDING

Overall Result

The Mininet network is working, and the exam was tested successfully at least once. The TCP connection test needs confirmation, and SDN forwarding still needs to be checked properly.
