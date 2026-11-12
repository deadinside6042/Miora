"""Conversation-mode selection for Miora.

This module does not provide mental-health diagnoses. It selects a response
posture from the latest message and recent dialogue, keeping conversational
judgment separate from retrieved subject-matter knowledge.
"""
import re


def build_conversation_guidance(messages: list) -> str:
    user_messages = [m.content.strip() for m in messages if m.role == "user"]
    assistant_messages = [m.content.strip() for m in messages if m.role == "assistant"]
    latest = user_messages[-1] if user_messages else ""
    previous_assistant = assistant_messages[-1] if assistant_messages else ""
    text = latest.lower()

    # Short answers must be interpreted in the context of the question just asked.
    short_follow_up = len(latest.split()) <= 8 and bool(previous_assistant)
    if short_follow_up:
        return (
            "MODE: CONTEXTUAL FOLLOW-THROUGH. The latest message is a short answer "
            "to something Miora just said. Interpret it in that context. Accept the "
            "answer; do not ask the same question again in different words. If the "
            "person says 'all of it', 'everything', 'I don't know', or similar, "
            "acknowledge that answer and respond to its meaning. Do not demand that "
            "they rank, narrow, or explain their feelings. A supportive statement "
            "may be the complete response."
        )

    if re.search(r"\b(suicid|kill myself|end my life|hurt myself|self[- ]harm|"
                 r"hurt someone|kill someone|in immediate danger)\b", text):
        return (
            "MODE: SAFETY-FOCUSED SUPPORT. Respond calmly and directly, assess "
            "immediate danger with one clear question when needed, and prioritize "
            "immediate human support and local emergency/crisis resources. Do not "
            "bury the safety response in general emotional reflection."
        )

    if re.search(r"\b(technique|exercise|strategy|tips?|steps|how do i cope|"
                 r"teach me|show me how|practice)\b", text):
        return (
            "MODE: REQUESTED SKILL OR TECHNIQUE. The person has asked for a method. "
            "Use relevant evidence-based knowledge if available, explain one "
            "appropriate option plainly, and offer a manageable way to try it. "
            "Do not overload them with several techniques."
        )

    if re.search(r"\b(what should i do|what do i do|how should i|help me decide|"
                 r"what are my options|what would you recommend)\b", text):
        return (
            "MODE: REQUESTED GUIDANCE. Answer the actual decision or problem. "
            "Use relevant knowledge, distinguish facts from possibilities, and "
            "offer one proportionate next step or a small set of genuinely useful "
            "options. Do not give generic coping advice."
        )

    if re.search(r"\b(why does|why do i|what does it mean|help me understand|"
                 r"what is happening|what's happening|what is going on)\b", text):
        return (
            "MODE: UNDERSTANDING AND INTERPRETATION. Use relevant subject knowledge "
            "to explain plausible patterns carefully. Be tentative, separate "
            "observable facts from hypotheses, and avoid diagnosing the person "
            "or anyone they describe."
        )

    if re.search(r"\b(i got the job|i passed|i did it|good news|promoted|"
                 r"we got engaged|i'm pregnant|im pregnant|i won)\b", text):
        return (
            "MODE: POSITIVE NEWS. Celebrate the specific achievement or good news. "
            "Do not turn it into assessment, advice, or a question by default."
        )

    if re.search(r"\b(just letting you know|just an update|went shopping|"
                 r"got groceries|watched a movie|at work|heading home)\b", text):
        return (
            "MODE: ORDINARY CONVERSATION. Respond naturally to the update. "
            "Do not infer distress or force a counselling frame."
        )

    return (
        "MODE: EMOTIONAL ATTUNEMENT / LISTENING. Unless the person clearly asks "
        "for advice or information, begin with a specific acknowledgement of "
        "what their words suggest and why it may matter. Do not supply a coping "
        "technique, lesson, checklist, or action plan by default. Avoid reflexive "
        "questions. If the person is overwhelmed, make the conversation feel "
        "lighter, not like another task. Let the response end after a meaningful "
        "reflection when that is enough."
    )
