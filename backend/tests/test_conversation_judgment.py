"""Tests for Miora's deterministic conversation judgment."""
import unittest
from types import SimpleNamespace

from conversation_judgment import analyze_conversation, build_conversation_guidance


def turn(role, content):
    return SimpleNamespace(role=role, content=content)


class ConversationJudgmentTests(unittest.TestCase):
    def test_safety_pattern_matches_real_language(self):
        plan = analyze_conversation([turn("user", "I'm thinking about suicide")])
        self.assertTrue(plan["safety_override"])
        self.assertEqual(plan["primary_job"], "safety_support")

    def test_safety_overrides_short_follow_up(self):
        plan = analyze_conversation([
            turn("assistant", "Are you thinking about hurting yourself right now?"),
            turn("user", "Yes"),
        ])
        self.assertEqual(plan["primary_job"], "safety_follow_through")
        self.assertTrue(plan["safety_override"])

    def test_all_of_it_is_accepted_as_contextual_follow_through(self):
        plan = analyze_conversation([
            turn("assistant", "Which of those feels most heavy right now?"),
            turn("user", "All of it"),
        ])
        self.assertTrue(plan["contextual_follow_through"])
        guidance = build_conversation_guidance([
            turn("assistant", "Which of those feels most heavy right now?"),
            turn("user", "All of it"),
        ])
        self.assertIn("do not restart the conversation", guidance.lower())

    def test_longer_answer_to_previous_question_keeps_context(self):
        plan = analyze_conversation([
            turn("assistant", "What happened?"),
            turn("user", "I should have known better. I've done this a hundred times."),
        ])
        self.assertTrue(plan["contextual_follow_through"])

    def test_repeated_questions_are_flagged(self):
        plan = analyze_conversation([
            turn("assistant", "What happened?"),
            turn("user", "It was a stupid mistake."),
            turn("assistant", "What happened?"),
            turn("user", "I've done this a hundred times."),
        ])
        self.assertTrue(plan["repeated_question_risk"])

    def test_work_mistake_signals_are_tentative(self):
        plan = analyze_conversation([
            turn("user", "It was such a stupid mistake. I should have known better.")
        ])
        self.assertIn("self_criticism", plan["possible_emotion_signals"])
        self.assertIn("tentative", build_conversation_guidance([
            turn("user", "It was such a stupid mistake. I should have known better.")
        ]).lower())

    def test_explicit_technique_request_selects_skill_mode(self):
        plan = analyze_conversation([turn("user", "Can you give me a grounding exercise?")])
        self.assertEqual(plan["primary_job"], "requested_skill")

    def test_unsolicited_emotional_disclosure_selects_listening(self):
        plan = analyze_conversation([turn("user", "I feel lonely and inadequate.")])
        self.assertEqual(plan["primary_job"], "acknowledge_and_listen")
        self.assertEqual(plan["advice_gate"], "open_on_request_only")


if __name__ == "__main__":
    unittest.main()
