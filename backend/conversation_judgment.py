"""Lightweight, deterministic conversation judgment for Miora.

This layer classifies the response job before generation. It is deliberately
heuristic: it provides structured guidance to the main model, not a diagnosis
or a claim to know the user's internal state.
"""
import json
import re
from difflib import SequenceMatcher


SAFETY = re.compile(
    r"\b(suicid\w*|kill myself|end my life|hurt(?:ing)? myself|hurt(?:ing)? yourself|self[- ]harm|"
    r"hurt someone|kill someone|in immediate danger|can't keep myself safe)\b",
    re.IGNORECASE,
)
SKILL_REQUEST = re.compile(
    r"\b(technique|exercise|strategy|tips?|steps|how do i cope|teach me|"
    r"show me how|practice|tool to help)\b", re.IGNORECASE
)
ADVICE_REQUEST = re.compile(
    r"\b(what should i do|what do i do|how should i|help me decide|"
    r"what are my options|what would you recommend|how can i fix)\b",
    re.IGNORECASE,
)
INTERPRETATION_REQUEST = re.compile(
    r"\b(why does|why do i|what does it mean|help me understand|"
    r"what is happening|what's happening|what is going on)\b",
    re.IGNORECASE,
)
POSITIVE_NEWS = re.compile(
    r"\b(i got the job|i passed|i did it|good news|promoted|"
    r"we got engaged|i'm pregnant|im pregnant|i won)\b", re.IGNORECASE
)
ORDINARY_UPDATE = re.compile(
    r"\b(just letting you know|just an update|went shopping|got groceries|"
    r"watched a movie|heading home)\b", re.IGNORECASE
)
INTENSITY_MARKERS = re.compile(
    r"\b(can't cope|cannot cope|breaking down|desperate|terrified|"
    r"completely overwhelmed|can't go on|at the end of my rope)\b",
    re.IGNORECASE,
)
EMOTION_TERMS = {
    "embarrassment": re.compile(r"\b(embarrass\w*|ashamed|humiliat\w*)\b", re.I),
    "frustration": re.compile(r"\b(frustrat\w*|annoyed|pissed off|fed up)\b", re.I),
    "self_criticism": re.compile(r"\b(stupid|idiot|my fault|should have known|"
                                 r"should've known|incompetent|useless)\b", re.I),
    "worry": re.compile(r"\b(worried|scared|afraid|nervous|anxious)\b", re.I),
    "sadness": re.compile(r"\b(sad|lonely|hurt|heartbroken|miserable)\b", re.I),
    "anger": re.compile(r"\b(angry|furious|rage|hate)\b", re.I),
}


def _content(message):
    value = getattr(message, "content", "")
    return value.strip() if isinstance(value, str) else ""


def _role(message):
    return getattr(message, "role", "")


def _question_text(message):
    content = _content(message)
    if "?" not in content:
        return ""
    return re.sub(r"\s+", " ", content.split("?")[-2] + "?").strip()


def analyze_conversation(messages: list) -> dict:
    """Return a compact response-plan snapshot based on recent dialogue."""
    recent = list(messages or [])[-8:]
    user_messages = [m for m in recent if _role(m) == "user"]
    assistant_messages = [m for m in recent if _role(m) == "assistant"]
    latest = _content(user_messages[-1]) if user_messages else ""
    previous_assistant = _content(assistant_messages[-1]) if assistant_messages else ""
    previous_lower = previous_assistant.lower()
    lower = latest.lower()

    safety_now = bool(SAFETY.search(latest))
    safety_follow_through = (
        not safety_now and len(latest.split()) <= 12
        and bool(SAFETY.search(previous_assistant))
    )
    contextual_follow_through = (
        bool(previous_assistant)
        and previous_assistant.rstrip().endswith("?")
        and not safety_now
        and not safety_follow_through
    )

    questions = [_question_text(m) for m in assistant_messages[-5:]]
    questions = [q for q in questions if q]
    repeated_question_risk = False
    if len(questions) >= 2:
        latest_q = questions[-1].lower()
        repeated_question_risk = any(
            SequenceMatcher(None, latest_q, prior.lower()).ratio() >= 0.72
            for prior in questions[:-1]
        )

    if safety_now:
        primary_job = "safety_support"
    elif safety_follow_through:
        primary_job = "safety_follow_through"
    elif SKILL_REQUEST.search(latest):
        primary_job = "requested_skill"
    elif ADVICE_REQUEST.search(latest):
        primary_job = "requested_guidance"
    elif INTERPRETATION_REQUEST.search(latest):
        primary_job = "understanding"
    elif POSITIVE_NEWS.search(latest):
        primary_job = "celebrate"
    elif ORDINARY_UPDATE.search(latest):
        primary_job = "ordinary_conversation"
    elif contextual_follow_through:
        primary_job = "contextual_follow_through"
    else:
        primary_job = "acknowledge_and_listen"

    emotions = [
        label for label, pattern in EMOTION_TERMS.items()
        if pattern.search(latest)
    ]
    if not emotions and contextual_follow_through:
        emotions = [
            label for label, pattern in EMOTION_TERMS.items()
            if pattern.search(" ".join(_content(m) for m in recent[-6:]))
        ]

    if safety_now or safety_follow_through:
        intensity = "safety_override"
    elif INTENSITY_MARKERS.search(latest):
        intensity = "high"
    elif any(word in lower for word in ("really", "so ", "can't", "cannot")):
        intensity = "moderate_or_unclear"
    else:
        intensity = "ordinary_or_unclear"

    if primary_job in ("safety_support", "safety_follow_through"):
        reply_goal = "assess immediate safety and connect to appropriate human support"
    elif primary_job in ("requested_skill", "requested_guidance"):
        reply_goal = "answer the explicit request with one proportionate, evidence-informed option"
    elif primary_job == "understanding":
        reply_goal = "explain plausible patterns tentatively and separate facts from hypotheses"
    elif primary_job == "celebrate":
        reply_goal = "recognize the specific positive event without turning it into an assessment"
    elif primary_job == "ordinary_conversation":
        reply_goal = "respond naturally without imposing a counselling frame"
    elif contextual_follow_through:
        reply_goal = "use the prior question and earlier details; acknowledge the answer and move the conversation forward"
    else:
        reply_goal = "show specific understanding, then leave room; do not rush into advice"

    return {
        "primary_job": primary_job,
        "safety_override": safety_now or safety_follow_through,
        "explicit_request": primary_job in ("requested_skill", "requested_guidance", "understanding"),
        "contextual_follow_through": contextual_follow_through or safety_follow_through,
        "recent_question_count": len(questions),
        "repeated_question_risk": repeated_question_risk,
        "possible_emotion_signals": emotions,
        "intensity": intensity,
        "advice_gate": "open_on_request_only" if primary_job not in (
            "requested_skill", "requested_guidance", "safety_support",
            "safety_follow_through"
        ) else "requested_or_safety_relevant",
        "reply_goal": reply_goal,
    }


def build_conversation_guidance(messages: list) -> str:
    plan = analyze_conversation(messages)
    job = plan["primary_job"]

    directives = {
        "safety_support": (
            "SAFETY-FOCUSED SUPPORT. Respond calmly and directly. Assess immediate "
            "danger with one clear question when needed, and prioritize immediate "
            "human support and local emergency/crisis resources."
        ),
        "safety_follow_through": (
            "SAFETY FOLLOW-THROUGH. Interpret the short answer in the context of "
            "the safety question just asked. Follow the safety protocol directly."
        ),
        "requested_skill": (
            "REQUESTED SKILL OR TECHNIQUE. Use relevant evidence-informed knowledge, "
            "explain one suitable option plainly, and do not overload the person."
        ),
        "requested_guidance": (
            "REQUESTED GUIDANCE. Answer the actual decision or problem. Distinguish "
            "facts from possibilities and offer one proportionate next step."
        ),
        "understanding": (
            "UNDERSTANDING AND INTERPRETATION. Explain plausible patterns carefully. "
            "Be tentative, separate observable facts from hypotheses, and do not diagnose."
        ),
        "celebrate": (
            "POSITIVE NEWS. Celebrate the specific achievement. Do not turn it into "
            "assessment, advice, or a question by default."
        ),
        "ordinary_conversation": (
            "ORDINARY CONVERSATION. Respond naturally. Do not infer distress or force "
            "a counselling frame."
        ),
        "contextual_follow_through": (
            "CONTEXTUAL FOLLOW-THROUGH. Treat the latest message as an answer to the "
            "previous question. Use the details already shared; do not restart the "
            "conversation or ask the same question in different words."
        ),
        "acknowledge_and_listen": (
            "EMOTIONAL ATTUNEMENT / LISTENING. Begin with a specific acknowledgement "
            "of what the person actually said and why it may matter. Do not supply "
            "a technique, lesson, checklist, or action plan unless requested."
        ),
    }

    return (
        "STRUCTURED CONVERSATION JUDGMENT (heuristic guidance, not diagnosis):\n"
        + json.dumps(plan, ensure_ascii=False, sort_keys=True)
        + "\nPRIMARY RESPONSE JOB: " + directives[job]
        + "\nCONVERSATIONAL CONTINUITY: Read the last several turns as one exchange. "
          "If the person has already answered a question, build on the answer rather "
          "than asking for the same information again. Use concrete details from "
          "their messages; do not merely repeat an emotion label.\n"
        + "NATURALNESS: Avoid stock counselling phrases and clinical-sounding "
          "interpretations when ordinary language will do. Do not inflate a small "
          "mistake into a major emotional burden. Acknowledge the event, not just "
          "the presumed feeling. Ask at most one useful question, and only if its "
          "answer changes what you should say next. A statement can be a complete reply.\n"
        + "REPETITION GATE: " + (
            "Recent assistant questions appear repetitive. Do not ask another "
            "version of a question already asked; change direction or make a "
            "specific observation instead."
            if plan["repeated_question_risk"] else
            "Check recent assistant turns before asking anything; avoid repeating "
            "a question or reflection."
        )
        + "\nADVICE GATE: " + plan["advice_gate"] + ". Do not give unsolicited fixes.\n"
        + "EMOTION SIGNALS: Treat any listed signals as tentative clues, not facts. "
          "Do not state them as a diagnosis or over-explain them."
    )
