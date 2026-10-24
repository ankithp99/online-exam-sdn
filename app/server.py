import socket
import threading
import json
import time

# Server configuration
HOST = "0.0.0.0"
PORT = 5000
EXAM_DURATION = 120  # Exam duration in seconds

# Exam questions
QUESTIONS = [
    {
        "question": "Which language is used for system programming?",
        "options": ["A. HTML", "B. C", "C. CSS", "D. SQL"],
        "answer": "B"
    },
    {
        "question": "Which protocol provides reliable communication?",
        "options": ["A. UDP", "B. IP", "C. TCP", "D. ARP"],
        "answer": "C"
    },
    {
        "question": "What does SDN stand for?",
        "options": [
            "A. Software Defined Networking",
            "B. System Data Network",
            "C. Secure Digital Node",
            "D. Simple Data Navigation"
        ],
        "answer": "A"
    },
    {
        "question": "Which data structure follows FIFO?",
        "options": ["A. Stack", "B. Queue", "C. Tree", "D. Graph"],
        "answer": "B"
    },
    {
        "question": "Which protocol is connectionless?",
        "options": ["A. TCP", "B. HTTP", "C. FTP", "D. UDP"],
        "answer": "D"
    }
]


def send_message(connection, message):
    """Send one JSON message followed by a newline."""
    data = json.dumps(message) + "\n"
    connection.sendall(data.encode("utf-8"))


def receive_message(reader):
    """Receive one JSON message."""
    line = reader.readline()

    if not line:
        return None

    return json.loads(line)


def handle_client(connection, address):
    """Handle one examination client."""
    print(f"[CONNECTED] Client {address}")

    reader = None

    try:
        reader = connection.makefile("r", encoding="utf-8")

        # Ask the student for their name
        send_message(connection, {
            "type": "welcome",
            "message": "Welcome to the Online Examination Network!"
        })

        message = receive_message(reader)

        if not message or message.get("type") != "register":
            send_message(connection, {
                "type": "error",
                "message": "Please register before starting the exam."
            })
            return

        student_name = str(message.get("name", "Student")).strip()

        if not student_name:
            student_name = "Student"

        print(f"[EXAM STARTED] Student: {student_name}")

        # Start the examination timer
        start_time = time.time()
        score = 0
        answers = []

        send_message(connection, {
            "type": "exam_started",
            "message": f"Exam started! You have {EXAM_DURATION} seconds.",
            "duration": EXAM_DURATION,
            "total_questions": len(QUESTIONS)
        })

        # Send questions one by one
        for index, question in enumerate(QUESTIONS):
            elapsed = time.time() - start_time
            remaining = max(0, int(EXAM_DURATION - elapsed))

            if remaining <= 0:
                break

            send_message(connection, {
                "type": "question",
                "number": index + 1,
                "total": len(QUESTIONS),
                "question": question["question"],
                "options": question["options"],
                "time_remaining": remaining
            })

            # Receive the student's answer
            message = receive_message(reader)

            if message is None:
                print(f"[DISCONNECTED] {student_name}")
                return

            # Check the timer after receiving the answer
            elapsed = time.time() - start_time

            if elapsed > EXAM_DURATION:
                break

            answer = str(message.get("answer", "")).strip().upper()

            if answer not in ["A", "B", "C", "D"]:
                answer = ""

            correct = answer == question["answer"]

            if correct:
                score += 1

            answers.append({
                "question": index + 1,
                "submitted_answer": answer or "Not answered",
                "correct": correct
            })

            send_message(connection, {
                "type": "answer_received",
                "message": "Answer recorded.",
                "correct": correct
            })

        # Calculate final result
        elapsed = int(time.time() - start_time)
        percentage = (score / len(QUESTIONS)) * 100

        send_message(connection, {
            "type": "result",
            "student": student_name,
            "score": score,
            "total": len(QUESTIONS),
            "percentage": round(percentage, 2),
            "time_taken": elapsed,
            "answers_recorded": len(answers)
        })

        print(
            f"[RESULT] {student_name}: "
            f"{score}/{len(QUESTIONS)} ({percentage:.2f}%)"
        )

    except (ConnectionResetError, BrokenPipeError):
        print(f"[CONNECTION ERROR] Client {address} disconnected.")

    except (json.JSONDecodeError, OSError) as error:
        print(f"[ERROR] Client {address}: {error}")

    except Exception as error:
        print(f"[UNEXPECTED ERROR] Client {address}: {error}")

    finally:
        if reader is not None:
            reader.close()

        connection.close()
        print(f"[DISCONNECTED] Client {address}")


def start_server():
    """Start the TCP examination server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Allow the port to be reused after restarting the server
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, PORT))
    server.listen(10)

    print("=" * 50)
    print(" ONLINE EXAMINATION NETWORK SERVER")
    print("=" * 50)
    print(f"Listening on {HOST}:{PORT}")
    print("Waiting for students to connect...")
    print("Press Ctrl+C to stop the server.")
    print("=" * 50)

    try:
        while True:
            connection, address = server.accept()

            # Each student gets a separate thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(connection, address),
                daemon=True
            )

            client_thread.start()

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")

    finally:
        server.close()


if __name__ == "__main__":
    start_server()
