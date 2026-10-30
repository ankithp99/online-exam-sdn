
import json
import unittest


class ExamProtocolTests(unittest.TestCase):
    """Basic tests for the online examination JSON protocol."""

    def encode_decode(self, message):
        """Simulate JSON serialization and deserialization."""
        encoded = json.dumps(message)
        return json.loads(encoded)

    def test_registration_message(self):
        message = {
            "type": "register",
            "name": "TestStudent"
        }

        decoded = self.encode_decode(message)

        self.assertEqual(decoded["type"], "register")
        self.assertEqual(decoded["name"], "TestStudent")

    def test_answer_message(self):
        message = {
            "type": "answer",
            "question_number": 1,
            "answer": "B"
        }

        decoded = self.encode_decode(message)

        self.assertEqual(decoded["type"], "answer")
        self.assertEqual(decoded["question_number"], 1)
        self.assertIn(decoded["answer"], ["A", "B", "C", "D"])

    def test_invalid_answer_is_not_a_valid_option(self):
        message = {
            "type": "answer",
            "question_number": 1,
            "answer": "X"
        }

        decoded = self.encode_decode(message)

        self.assertNotIn(decoded["answer"], ["A", "B", "C", "D"])

    def test_result_message(self):
        message = {
            "type": "result",
            "score": 4,
            "total": 5,
            "percentage": 80.0
        }

        decoded = self.encode_decode(message)

        self.assertEqual(decoded["type"], "result")
        self.assertEqual(decoded["score"], 4)
        self.assertEqual(decoded["total"], 5)
        self.assertEqual(decoded["percentage"], 80.0)


if __name__ == "__main__":
    unittest.main()

