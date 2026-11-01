# ExamNet browser interface

The login and exam pages live in this folder and are served by
`app/web_api.py`. The bridge connects the browser to the existing TCP exam
server. That server provides questions, enforces the exam deadline, accepts
answers, and calculates the result. The interface preserves visited questions
and review marks in the current browser tab if it is refreshed. Submitted
answers cannot be changed because the TCP protocol accepts them one at a time.

Candidate ID is a display label only; the project does not authenticate
candidate identities. When the server-enforced deadline expires, the browser
requests the final result from the TCP exam server automatically.

## Run locally on Ubuntu

From the project root, open one terminal for the exam server:

```bash
python3 app/server.py
```

Open a second terminal in the project root:

```bash
python3 app/web_api.py
```

Visit `http://127.0.0.1:8080`. The bridge health endpoint is
`http://127.0.0.1:8080/api/health`. Do not use `python3 -m http.server`; it
serves files but cannot handle the exam API requests.

## Run through Mininet

Start OS-Ken and Mininet using `docs/README.md`. At the Mininet prompt:

```text
mininet> h1 python3 app/server.py > /tmp/exam-server.log 2>&1 &
mininet> h1 python3 app/web_api.py > /tmp/exam-web.log 2>&1 &
```

The browser can run on the Ubuntu desktop. While Mininet is active, add a
temporary management address to the OVS bridge from a regular Ubuntu terminal:

```bash
sudo ip link set s1 up
sudo ip addr replace 10.0.0.254/24 dev s1
sudo ip route replace 10.0.0.0/24 dev s1 src 10.0.0.254
```

Open `http://10.0.0.1:8080` in the desktop browser. This avoids launching a
Snap-packaged browser inside a Mininet network namespace. Remove the temporary
route and address after stopping Mininet:

```bash
sudo ip route del 10.0.0.0/24 dev s1
sudo ip addr del 10.0.0.254/24 dev s1
```

For a host-specific connectivity check, run
`h2 curl http://10.0.0.1:8080/api/health` at the Mininet prompt. The bridge is
for project demonstration, not an authenticated or production exam service.
