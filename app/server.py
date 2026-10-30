
import json
import socket
import threading
import time
import select

HOST = "0.0.0.0"
PORT = 5000
EXAM_DURATION = 120
REGISTRATION_TIMEOUT = 60
MAX_CONCURRENT_CLIENTS = 20
CLIENT_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_CLIENTS)

QUESTIONS = [
    {
        "question": "Which language is used for system programming?",
        "options": ["A. HTML", "B. C", "C. CSS", "D. SQL"],
        "answer": "B",
    },
    {
        "question": "Which protocol provides reliable communication?",
        "options": ["A. UDP", "B. IP", "C. TCP", "D. ARP"],
        "answer": "C",
    },
    {
        "question": "What does SDN stand for?",
        "options": [
            "A. Software Defined Networking",
            "B. System Data Network",
            "C. Secure Digital Node",
            "D. Simple Data Navigation",
        ],
        "answer": "A",
    },
    {
        "question": "Which data structure follows FIFO?",
        "options": ["A. Stack", "B. Queue", "C. Tree", "D. Graph"],
        "answer": "B",
    },
    {
        "question": "Which protocol is connectionless?",
        "options": ["A. TCP", "B. HTTP", "C. FTP", "D. UDP"],
        "answer": "D",
    },
]


def send_message(connection, message):
    """Send a JSON message followed by a newline."""
    payload = json.dumps(message) + "\n"
    connection.sendall(payload.encode("utf-8"))


def receive_message(connection, state, deadline):
    """
    Receive one newline-delimited JSON message before a monotonic deadline.
    Uses the raw socket consistently to avoid buffered-reader/select issues.
    """
    while True:
        if b"\n" in state["buffer"]:
            line, _, remainder = state["buffer"].partition(b"\n")
            state["buffer"] = bytearray(remainder)

            if not line.strip():
                continue

            return json.loads(line.decode("utf-8"))

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Deadline expired")

        readable, _, _ = select.select(
            [connection], [], [], remaining
        )
        if not readable:
            raise TimeoutError("Deadline expired")

        chunk = connection.recv(4096)
        if not chunk:
            return None

        state["buffer"].extend(chunk)


def handle_client(connection, address):
    student_name = "Student"
    state = {"buffer": bytearray()}
    start_time = None
    score = 0
    answers = []

    print(f"[CONNECTED] {address}")

    try:
        connection.setblocking(True)
        send_message(connection, {
            "type": "welcome",
            "message": "Welcome to the Online Examination Network.",
        })

        try:
            message = receive_message(
                connection,
                state,
                time.monotonic() + REGISTRATION_TIMEOUT,
            )
        except TimeoutError:
            print(f"[TIMEOUT] Registration timed out for {address}")
            return

        if not isinstance(message, dict) or message.get("type") != "register":
            send_message(connection, {
                "type": "error",
                "message": "Valid registration is required.",
            })
            return

        student_name = str(message.get("name", "Student")).strip() or "Student"
        start_time = time.monotonic()
        deadline = start_time + EXAM_DURATION

        send_message(connection, {
            "type": "exam_started",
            "duration": EXAM_DURATION,
            "message": "Exam started. Good luck!",
        })

        for index, question in enumerate(QUESTIONS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print(f"[TIMEOUT] Exam expired for {student_name}")
                break

            send_message(connection, {
                "type": "question",
                "number": index + 1,
                "total": len(QUESTIONS),
                "question": question["question"],
                "options": question["options"],
                "time_remaining": max(0, int(remaining)),
            })

            try:
                message = receive_message(connection, state, deadline)
            except TimeoutError:
                print(f"[TIMEOUT] No answer before deadline: {student_name}")
                break

            if message is None:
                print(f"[DISCONNECTED] {student_name}")
                return

            # Reject an answer if the deadline passed while it was received.
            if time.monotonic() >= deadline:
                print(f"[LATE ANSWER REJECTED] {student_name}")
                break

            if not isinstance(message, dict) or message.get("type") != "answer":
                answer = ""
            else:
                answer = str(message.get("answer", "")).strip().upper()

            if answer not in ("A", "B", "C", "D"):
                answer = ""

            correct = answer == question["answer"]
            if correct:
                score += 1

            answers.append({
                "question": index + 1,
                "submitted_answer": answer or "Not answered",
                "correct": correct,
            })

            send_message(connection, {
                "type": "answer_received",
                "message": "Answer recorded.",
            })

        elapsed = 0
        if start_time is not None:
            elapsed = min(
                int(time.monotonic() - start_time),
                EXAM_DURATION,
            )

        result = {
            "type": "result",
            "student": student_name,
            "score": score,
            "total": len(QUESTIONS),
            "percentage": round(score / len(QUESTIONS) * 100, 2),
            "time_taken": elapsed,
            "answers_recorded": len(answers),
        }

        send_message(connection, result)
        print(
            f"[RESULT] {student_name}: {score}/{len(QUESTIONS)} "
            f"({result['percentage']}%)"
        )

    except (ConnectionResetError, BrokenPipeError):
        print(f"[DISCONNECTED] {student_name} disconnected unexpectedly.")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[INVALID MESSAGE] {address}: {exc}")
    except OSError as exc:
        print(f"[SOCKET ERROR] {address}: {exc}")
    except Exception as exc:
        print(f"[ERROR] {address}: {exc}")
    finally:
        connection.close()
        print(f"[CLOSED] {address}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((HOST, PORT))
        server.listen(10)

        print("=" * 50)
        print("ONLINE EXAMINATION NETWORK SERVER")
        print("=" * 50)
        print(f"Listening on {HOST}:{PORT}")
        print(f"Exam duration: {EXAM_DURATION} seconds")
        print("Waiting for students to connect...")
        print("Press Ctrl+C to stop the server.")

        while True:
            connection, address = server.accept()
            if not CLIENT_SLOTS.acquire(blocking=False):
                try:
                    send_message(connection, {
                        "type": "error",
                        "message": "The exam server is full. Please try again shortly.",
                    })
                except OSError:
                    pass
                finally:
                    connection.close()
                print(f"[BUSY] Rejected connection from {address}")
                continue

            thread = threading.Thread(
                target=serve_client,
                args=(connection, address),
                daemon=True,
            )
            thread.start()

    except KeyboardInterrupt:
        print("\nServer shutting down.")
    except OSError as exc:
        print(f"Server socket error: {exc}")
    finally:
        server.close()


def serve_client(connection, address):
    """Run one exam session and always return its capacity slot."""
    try:
        handle_client(connection, address)
    finally:
        CLIENT_SLOTS.release()


if __name__ == "__main__":
    start_server()

