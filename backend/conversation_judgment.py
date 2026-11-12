"""Conversation-mode selection for Miora.

Selects a response posture from the latest message and recent dialogue.
Subject-matter knowledge is retrieved separately and must not dictate tone.
"""
import re


SAFETY = re.compile(
    r"\\b(suicid|kill myself|end my life|hurt myself|self[- ]harm|"
    r"hurt someone|kill someone|in immediate danger)\\b",
    re.IGNORECASE,
)


def build_conversation_guidance(messages: list) -> str:
    user_messages = [m.content.strip() for m in messages if m.role == "user"]
    assistant_messages = [m.content.strip() for m in messages if m.role == "assistant"]
    latest = user_messages[-1] if user_messages else ""
    previous_assistant = assistant_messages[-1] if assistant_messages else ""
    text = latest.lower()

    # Safety is always higher priority than ordinary conversational flow.
    if SAFETY.search(latest):
        return (
            "MODE: SAFETY-FOCUSED SUPPORT. Respond calmly and directly, assess "
            "immediate danger with one clear question when needed, and prioritize "
            "immediate human support and local emergency/crisis resources."
        )

    # Short answers are meaningful in the context of the question just asked.
    if len(latest.split()) <= 8 and previous_assistant:
        if SAFETY.search(previous_assistant):
            return (
                "MODE: SAFETY FOLLOW-THROUGH. Interpret this short answer in the "
                "context of the immediate-safety question just asked. Follow the "
                "safety protocol directly; do not switch to ordinary reflection."
            )
        return (
            "MODE: CONTEXTUAL FOLLOW-THROUGH. Interpret the latest short message "
            "as an answer to Miora's previous turn. Accept it; do not repeat the "
            "same question in different words. If the person says 'all of it', "
            "'everything', or 'I don't know', acknowledge that answer and respond "
            "to its meaning. Do not make them rank or narrow their feelings. A "
            "supportive statement may be the complete response."
        )

    if re.search(r"\\b(technique|exercise|strategy|tips?|steps|how do i cope|"
                 r"teach me|show me how|practice)\\b", text):
        return (
            "MODE: REQUESTED SKILL OR TECHNIQUE. Use relevant evidence-informed "
            "knowledge, explain one appropriate option plainly, and offer a "
            "manageable way to try it. Do not overload the person."
        )

    if re.search(r"\\b(what should i do|what do i do|how should i|help me decide|"
                 r"what are my options|what would you recommend)\\b", text):
        return (
            "MODE: REQUESTED GUIDANCE. Answer the actual decision or problem. "
            "Use relevant knowledge, distinguish facts from possibilities, and "
            "offer one proportionate next step. Avoid generic coping advice."
        )

    if re.search(r"\\b(why does|why do i|what does it mean|help me understand|"
                 r"what is happening|what's happening|what is going on)\\b", text):
        return (
            "MODE: UNDERSTANDING AND INTERPRETATION. Use relevant subject knowledge "
            "to explain plausible patterns carefully. Be tentative, separate "
            "observable facts from hypotheses, and do not diagnose."
        )

    if re.search(r"\\b(i got the job|i passed|i did it|good news|promoted|"
                 r"we got engaged|i'm pregnant|im pregnant|i won)\\b", text):
        return (
            "MODE: POSITIVE NEWS. Celebrate the specific achievement. Do not turn "
            "it into assessment, advice, or a question by default."
        )

    if re.search(r"\\b(just letting you know|just an update|went shopping|"
                 r"got groceries|watched a movie|at work|heading home)\\b", text):
        return (
            "MODE: ORDINARY CONVERSATION. Respond naturally. Do not infer distress "
            "or force a counselling frame."
        )

    return (
        "MODE: EMOTIONAL ATTUNEMENT / LISTENING. Unless the person clearly asks "
        "for advice or information, begin with a specific acknowledgement of "
        "what their words suggest and why it may matter. Do not supply a coping "
        "technique, lesson, checklist, or action plan by default. Avoid reflexive "
        "questions. If overwhelmed, make the conversation feel lighter, not like "
        "another task. Do not use retrieved knowledge merely because it is "
        "available; keep factual resources out of a listening reply unless they "
        "directly help answer what the person asked."
    )
