"""Tests for Miora's conversation-mode selection."""
import unittest
from types import SimpleNamespace

from conversation_judgment import build_conversation_guidance


def turn(role, content):
    return SimpleNamespace(role=role, content=content)


class ConversationJudgmentTests(unittest.TestCase):
    def test_all_of_it_is_accepted_without_repeating_question(self):
        guidance = build_conversation_guidance([
            turn("assistant", "Which of those feels most heavy right now?"),
            turn("user", "All of it"),
        ])
        self.assertIn("CONTEXTUAL FOLLOW-THROUGH", guidance)
        self.assertIn("Do not repeat the same question", guidance)

    def test_explicit_technique_request_selects_skill_mode(self):
        guidance = build_conversation_guidance([
            turn("user", "Can you give me a grounding exercise?")
        ])
        self.assertIn("REQUESTED SKILL OR TECHNIQUE", guidance)

    def test_safety_overrides_short_follow_up(self):
        guidance = build_conversation_guidance([
            turn("assistant", "Are you thinking about hurting yourself right now?"),
            turn("user", "Yes"),
        ])
        self.assertIn("SAFETY FOLLOW-THROUGH", guidance)

    def test_unsolicited_emotional_disclosure_selects_listening(self):
        guidance = build_conversation_guidance([
            turn("user", "I feel lonely and inadequate.")
        ])
        self.assertIn("EMOTIONAL ATTUNEMENT / LISTENING", guidance)
        self.assertIn("Do not use retrieved knowledge merely because it is available", guidance)


if __name__ == "__main__":
    unittest.main()
