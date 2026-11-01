"""HTTP bridge between the browser UI and the existing TCP exam server.

Run the exam TCP server and this bridge in the same network namespace. The
bridge keeps one TCP exam connection per browser session and exposes only the
current question and final server-scored result over HTTP.
"""

import json
import os
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


WEB_ROOT = Path(__file__).resolve().parent / "web"
LISTEN_HOST = os.getenv("WEB_API_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("WEB_API_PORT", "8080"))
EXAM_HOST = os.getenv("EXAM_SERVER_HOST", "127.0.0.1")
EXAM_PORT = int(os.getenv("EXAM_SERVER_PORT", "5000"))
EXAM_TIMEOUT = int(os.getenv("EXAM_API_TIMEOUT", "135"))
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


def expire_sessions():
    now = time.monotonic()
    with SESSIONS_LOCK:
        expired = [key for key, value in SESSIONS.items() if value["expires_at"] <= now]
        sessions = [SESSIONS.pop(key) for key in expired]
    for session in sessions:
        try:
            session["exam"].sock.close()
        except OSError:
            pass


class ExamConnection:
    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()
        self.lock = threading.Lock()

    def receive(self):
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Exam server closed the connection")
            self.buffer.extend(chunk)
        line, _, remainder = self.buffer.partition(b"\n")
        self.buffer = bytearray(remainder)
        return json.loads(line.decode("utf-8"))

    def send(self, message):
        self.sock.sendall((json.dumps(message) + "\n").encode("utf-8"))


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "ExamNetWeb/1.0"

    def log_message(self, fmt, *args):
        print("[WEB] " + fmt % args)

    def send_json(self, status, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 8192:
            raise ValueError("Request is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        expire_sessions()
        path = urlparse(self.path).path
        if path == "/api/health":
            try:
                with socket.create_connection((EXAM_HOST, EXAM_PORT), timeout=3) as sock:
                    sock.settimeout(3)
                    greeting = ExamConnection(sock).receive()
                if greeting.get("type") != "welcome":
                    raise ConnectionError("Unexpected greeting from exam server")
                return self.send_json(200, {"ok": True, "exam_server": EXAM_HOST + ":" + str(EXAM_PORT)})
            except (OSError, ConnectionError, ValueError) as exc:
                return self.send_json(503, {"ok": False, "error": "Exam server unavailable at " + EXAM_HOST + ":" + str(EXAM_PORT) + " (" + str(exc) + ")"})
        if path in ("/", "/index.html"):
            return self.serve_file("index.html", "text/html; charset=utf-8")
        if path in ("/exam.html", "/styles.css", "/app.js"):
            content_type = "text/html; charset=utf-8" if path.endswith(".html") else ("text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8")
            return self.serve_file(path.lstrip("/"), content_type)
        self.send_json(404, {"error": "Not found"})

    def serve_file(self, name, content_type):
        file_path = (WEB_ROOT / name).resolve()
        if WEB_ROOT.resolve() not in file_path.parents:
            return self.send_json(404, {"error": "Not found"})
        try:
            payload = file_path.read_bytes()
        except OSError:
            return self.send_json(404, {"error": "UI file not found"})
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        expire_sessions()
        path = urlparse(self.path).path
        if path == "/api/sessions":
            return self.create_session()
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "sessions" and parts[3] == "answer":
            return self.submit_answer(parts[2])
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "sessions" and parts[3] == "finish":
            return self.finish_session(parts[2])
        self.send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        expire_sessions()
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "sessions"]:
            return self.send_json(404, {"error": "Not found"})
        with SESSIONS_LOCK:
            session = SESSIONS.pop(parts[2], None)
        if session:
            session["exam"].sock.close()
        self.send_json(200, {"ok": True})

    def create_session(self):
        try:
            body = self.read_json()
            name = str(body.get("name", "")).strip()
            candidate_id = str(body.get("candidate_id", "")).strip()
            if not name or len(name) > 80 or not candidate_id or len(candidate_id) > 40:
                return self.send_json(400, {"error": "Enter a name and candidate ID within the allowed length."})
            sock = socket.create_connection((EXAM_HOST, EXAM_PORT), timeout=5)
            sock.settimeout(EXAM_TIMEOUT)
            exam = ExamConnection(sock)
            welcome = exam.receive()
            if welcome.get("type") != "welcome":
                raise ConnectionError("Unexpected greeting from exam server")
            exam.send({"type": "register", "name": name})
            started = exam.receive()
            if started.get("type") != "exam_started":
                raise ConnectionError(started.get("message", "Exam registration failed"))
            question = exam.receive()
            if question.get("type") != "question":
                raise ConnectionError("Exam server did not provide the first question")
            session_id = uuid.uuid4().hex
            with SESSIONS_LOCK:
                SESSIONS[session_id] = {
                    "exam": exam,
                    "name": name,
                    "candidate_id": candidate_id,
                    "expires_at": time.monotonic() + EXAM_TIMEOUT + 30,
                }
            return self.send_json(201, {
                "session_id": session_id,
                "candidate": name,
                "candidate_id": candidate_id,
                "duration": started.get("duration", 120),
                "question": self.public_question(question),
            })
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except (OSError, ConnectionError, KeyError) as exc:
            return self.send_json(503, {"error": "Could not start an exam session: " + str(exc)})

    def submit_answer(self, session_id):
        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)
        if not session:
            return self.send_json(404, {"error": "Exam session not found or already finished."})
        try:
            body = self.read_json()
            answer = str(body.get("answer", "")).strip().upper()
            if answer not in ("A", "B", "C", "D"):
                return self.send_json(400, {"error": "Choose A, B, C, or D."})
            exam = session["exam"]
            with exam.lock:
                exam.send({"type": "answer", "answer": answer})
                ack = exam.receive()
                if ack.get("type") == "result":
                    next_message = ack
                elif ack.get("type") != "answer_received":
                    raise ConnectionError(ack.get("message", "Answer was not accepted"))
                else:
                    next_message = exam.receive()
            if next_message.get("type") == "question":
                return self.send_json(200, {"question": self.public_question(next_message)})
            if next_message.get("type") == "result":
                with SESSIONS_LOCK:
                    SESSIONS.pop(session_id, None)
                exam.sock.close()
                return self.send_json(200, {"result": next_message})
            raise ConnectionError("Unexpected response from exam server")
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except (OSError, ConnectionError) as exc:
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
            try:
                session["exam"].sock.close()
            except OSError:
                pass
            return self.send_json(503, {"error": "Exam connection ended: " + str(exc)})

    def finish_session(self, session_id):
        """Wait for and return the exam server's deadline result."""
        with SESSIONS_LOCK:
            session = SESSIONS.get(session_id)
        if not session:
            return self.send_json(404, {"error": "Exam session not found or already finished."})
        exam = session["exam"]
        try:
            with exam.lock:
                result = exam.receive()
            if result.get("type") != "result":
                return self.send_json(409, {"error": "The exam server has not sent a final result yet."})
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
            exam.sock.close()
            return self.send_json(200, {"result": result})
        except (OSError, ConnectionError, ValueError, json.JSONDecodeError) as exc:
            with SESSIONS_LOCK:
                SESSIONS.pop(session_id, None)
            try:
                exam.sock.close()
            except OSError:
                pass
            return self.send_json(503, {"error": "Could not retrieve the timed result: " + str(exc)})

    @staticmethod
    def public_question(message):
        return {
            "number": message.get("number"),
            "total": message.get("total"),
            "question": message.get("question"),
            "options": message.get("options", []),
            "time_remaining": message.get("time_remaining"),
        }


def main():
    httpd = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), RequestHandler)
    httpd.daemon_threads = True
    print(f"ExamNet UI and API listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    print(f"TCP exam server: {EXAM_HOST}:{EXAM_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb API shutting down")
    finally:
        httpd.server_close()
        with SESSIONS_LOCK:
            sessions = list(SESSIONS.values())
            SESSIONS.clear()
        for session in sessions:
            session["exam"].sock.close()


if __name__ == "__main__":
    main()
