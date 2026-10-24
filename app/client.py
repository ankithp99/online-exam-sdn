import socket
import json

HOST = "10.0.0.1"
PORT = 5000


def send_message(connection, message):
    data = json.dumps(message) + "\n"
    connection.sendall(data.encode("utf-8"))


def receive_message(reader):
    line = reader.readline()

    if not line:
        return None

    return json.loads(line)


def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect((HOST, PORT))
        reader = client.makefile("r", encoding="utf-8")

        # Receive welcome message
        message = receive_message(reader)
        print("\n", message["message"])

        # Register student
        name = input("Enter your name: ").strip()

        send_message(client, {
            "type": "register",
            "name": name
        })

        # Receive exam start information
        message = receive_message(reader)

        if message is None:
            print("Server disconnected.")
            return

        if message["type"] != "exam_started":
            print(message.get("message", "Unable to start exam."))
            return

        print("\n" + message["message"])
        print("Total questions:", message["total_questions"])

        # Answer questions
        while True:
            message = receive_message(reader)

            if message is None:
                print("Server disconnected.")
                break

            if message["type"] == "question":
                print("\n" + "=" * 40)
                print(
                    f"Question {message['number']} "
                    f"of {message['total']}"
                )
                print(message["question"])

                for option in message["options"]:
                    print(option)

                print("Time remaining:", message["time_remaining"], "seconds")

                answer = input("Your answer (A/B/C/D): ").strip().upper()

                send_message(client, {
                    "type": "answer",
                    "answer": answer
                })

                feedback = receive_message(reader)

                if feedback is None:
                    print("Server disconnected.")
                    break

                if feedback["type"] == "answer_received":
                    print(feedback["message"])

            elif message["type"] == "result":
                print("\n" + "=" * 40)
                print("EXAM RESULT")
                print("=" * 40)
                print("Student:", message["student"])
                print(
                    "Score:",
                    str(message["score"]) + "/" + str(message["total"])
                )
                print("Percentage:", str(message["percentage"]) + "%")
                print("Time taken:", message["time_taken"], "seconds")
                print("=" * 40)
                break

            elif message["type"] == "error":
                print("Error:", message["message"])
                break

    except ConnectionRefusedError:
        print("Could not connect. Make sure the server is running.")

    except (ConnectionResetError, BrokenPipeError):
        print("The server disconnected unexpectedly.")

    except OSError as error:
        print("Network error:", error)

    finally:
        client.close()


if __name__ == "__main__":
    main()

