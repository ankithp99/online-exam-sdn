# Online Examination Network (TCP + Mininet + SDN)

Multi-user online exam over TCP sockets, emulated in Mininet and controlled by
an OS-Ken (OpenFlow 1.3) SDN controller with dynamic UDP congestion filtering.

| Item | Detail |
|---|---|
| Topology | h1 exam server (10.0.0.1), h2/h3 students, switch s1 |
| App | TCP port 5000, JSON messages, 5 MCQs, 120 s timer, max 20 clients |
| SDN | MAC learning + flow install; port-stats monitoring; UDP drop rule above 100 kbps, cleared below 50 kbps |
| Stack | Ubuntu, Python 3, Mininet 2.3.0, Open vSwitch, OS-Ken, iperf3 |

## Quick start
```bash
python3 -m venv .venv-osken31 && source .venv-osken31/bin/activate
pip install -r sdn/requirements.txt
osken-manager --ofp-tcp-listen-port 6653 sdn/ryu_controller.py        # terminal 1
sudo mn --custom mininet/topology.py --topo onlineexam \
  --switch ovsk,protocols=OpenFlow13 --controller remote,ip=127.0.0.1,port=6653   # terminal 2
mininet> pingall
mininet> h1 python3 app/server.py &
mininet> h2 python3 app/client.py
```

## Layout
`app/` server, client, web UI · `mininet/` topology · `sdn/` controller ·
`scripts/` iperf, bot and summary tools · `tests/` tests and test cases ·
`results/` measurements · `docs/README.md` full documentation.

## Tests
`python3 -m unittest discover -s tests -v` (unit and loopback integration).
Network tests, commands and results: `tests/test_cases.md`, `results/`.

Team: Prasanth Naidu, Ankith, Niketh B.P. — Computer Networks project 18.
