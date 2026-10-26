
import json
import queue
import socket
import threading

# Local Ubuntu testing: use "127.0.0.1".
# Mininet testing: change this to "10.0.0.1".
HOST = "10.0.0.1"
PORT = 5000


def send_message(sock, message):
    """Send one JSON message followed by a newline."""
    payload = json.dumps(message) + "\n"
    sock.sendall(payload.encode("utf-8"))


def receive_messages(sock, events, stop_event):
    """Receive server messages in a background thread."""
    buffer = bytearray()

    try:
        while not stop_event.is_set():
            chunk = sock.recv(4096)

            if not chunk:
                events.put(("closed", None))
                return

            buffer.extend(chunk)

            while b"\n" in buffer:
                line, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)

                if not line.strip():
                    continue

                try:
                    message = json.loads(line.decode("utf-8"))
                    events.put(("message", message))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    events.put(("error", "Invalid message received from server."))
                    return

    except (OSError, ConnectionError):
        if not stop_event.is_set():
            events.put(("closed", None))


def read_answer(events, question_id):
    """Read an answer without blocking the main client loop."""
    while True:
        try:
            answer = input("Your answer (A/B/C/D): ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            events.put(("input_cancelled", question_id))
            return

        if answer in ("A", "B", "C", "D"):
            events.put(("answer", (question_id, answer)))
            return

        print("Invalid option. Enter A, B, C, or D.")


def run_exam():
    events = queue.Queue()
    stop_event = threading.Event()

    current_question = None
    answered_questions = set()
    exam_finished = False
    student_name = ""

    try:
        with socket.create_connection((HOST, PORT), timeout=5) as sock:
            # Use blocking socket reads in the receiver thread.
            sock.settimeout(None)

            print("=" * 45)
            print("       ONLINE EXAMINATION CLIENT")
            print("=" * 45)

            # Receive the welcome message before registration.
            buffer = bytearray()

            while b"\n" not in buffer:
                chunk = sock.recv(4096)
                if not chunk:
                    print("Server closed the connection.")
                    return
                buffer.extend(chunk)

            line, _, remainder = buffer.partition(b"\n")
            buffer = bytearray(remainder)
            welcome = json.loads(line.decode("utf-8"))
            print(welcome.get("message", "Connected to exam server."))

            student_name = input("Enter your name: ").strip()
            while not student_name:
                print("Name cannot be empty.")
                student_name = input("Enter your name: ").strip()

            send_message(sock, {
                "type": "register",
                "name": student_name,
            })

            # Start receiving server messages independently of keyboard input.
            receiver = threading.Thread(
                target=receive_messages,
                args=(sock, events, stop_event),
                daemon=True,
            )
            receiver.start()

            print("\nWaiting for the examination to start...")

            while not exam_finished:
                try:
                    event_type, payload = events.get(timeout=0.2)
                except queue.Empty:
                    continue

                if event_type == "closed":
                    print("\nThe server connection was closed.")
                    break

                if event_type == "error":
                    print(f"\n{payload}")
                    break

                if event_type == "input_cancelled":
                    if payload == current_question:
                        print("\nAnswer input cancelled.")
                    continue

                if event_type == "answer":
                    question_id, answer = payload

                    # Never send an answer for an old question.
                    if (
                        current_question == question_id
                        and question_id not in answered_questions
                        and not exam_finished
                    ):
                        try:
                            send_message(sock, {
                                "type": "answer",
                                "answer": answer,
                            })
                            answered_questions.add(question_id)
                        except OSError:
                            print("\nCould not submit the answer.")
                            break

                    continue

                if event_type != "message":
                    continue

                message = payload
                message_type = message.get("type")

                if message_type == "exam_started":
                    print("\nExam started!")
                    print(
                        f"Duration: {message.get('duration', '?')} seconds"
                    )
                    print("Answer each question using A, B, C, or D.")

                elif message_type == "question":
                    current_question = message.get("number")

                    print("\n" + "-" * 45)
                    print(
                        f"Question {current_question} of "
                        f"{message.get('total', '?')}"
                    )
                    print(message.get("question", ""))

                    for option in message.get("options", []):
                        print(option)

                    remaining = message.get("time_remaining")
                    if remaining is not None:
                        print(f"Time remaining: {remaining} seconds")

                    if current_question not in answered_questions:
                        input_thread = threading.Thread(
                            target=read_answer,
                            args=(events, current_question),
                            daemon=True,
                        )
                        input_thread.start()

                elif message_type == "answer_received":
                    print(message.get("message", "Answer recorded."))

                elif message_type == "result":
                    exam_finished = True
                    stop_event.set()

                    print("\n" + "=" * 45)
                    print("              EXAM RESULT")
                    print("=" * 45)
                    print(f"Student: {message.get('student', student_name)}")
                    print(
                        f"Score: {message.get('score', 0)} / "
                        f"{message.get('total', 0)}"
                    )
                    print(f"Percentage: {message.get('percentage', 0)}%")
                    print(
                        f"Time taken: {message.get('time_taken', 0)} seconds"
                    )
                    print(
                        f"Answers recorded: "
                        f"{message.get('answers_recorded', 0)}"
                    )
                    print("=" * 45)
                    print("Examination finished.")

                elif message_type == "error":
                    print(
                        "\nServer error:",
                        message.get("message", "Unknown error"),
                    )
                    exam_finished = True

                elif message_type == "welcome":
                    # The initial welcome is handled before the receiver starts.
                    continue

                else:
                    print("Unexpected server message:", message)

    except ConnectionRefusedError:
        print("Could not connect. Make sure the server is running.")
        print(f"Server address: {HOST}:{PORT}")

    except socket.timeout:
        print("Connection timed out.")

    except (ConnectionError, BrokenPipeError, OSError) as exc:
        print(f"Connection problem: {exc}")

    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Received invalid data from the server.")

    except KeyboardInterrupt:
        print("\nExam client stopped.")

    except EOFError:
        print("\nInput ended. Exiting exam client.")

    finally:
        stop_event.set()


if __name__ == "__main__":
    run_exam()

