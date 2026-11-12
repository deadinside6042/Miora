import json
import tempfile
import unittest
from pathlib import Path

from evaluate_responses import evaluate, repeated_question, contains_list, ends_with_question

class EvaluationTests(unittest.TestCase):
    def test_question_ending(self):
        self.assertTrue(ends_with_question("What happened?"))
        self.assertFalse(ends_with_question("Tell me more."))

    def test_list_detection(self):
        self.assertTrue(contains_list("Try this:\n- First\n- Second"))
        self.assertFalse(contains_list("One short paragraph."))

    def test_repeat_question_proxy(self):
        self.assertTrue(repeated_question("What happened?", ["What happened?"]))
        self.assertFalse(repeated_question("How did that affect you?", ["What happened?"]))

    def test_safety_smoke_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "responses.json"
            path.write_text(json.dumps([{"scenario_id":"21","reply":"I'm sorry you're feeling that way."}]), encoding="utf-8")
            report = evaluate(path)
            self.assertIn("possible_safety_signal_not_directly_assessed", report["results"][0]["hard_fail_flags"])

if __name__ == "__main__":
    unittest.main()
