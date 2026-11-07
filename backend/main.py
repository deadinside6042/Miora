
import os
import json
import re
import urllib.request
import urllib.error
from typing import Literal, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="Miora Counselling Support API", version="1.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)
    conversation_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=2048)


class ProfileUpdate(BaseModel):
    preferred_name: Optional[str] = Field(default=None, max_length=80)
    memory_summary: Optional[str] = Field(default=None, max_length=6000)


SYSTEM_PROMPT = """
You are Miora, an evidence-informed counselling support system. Your role is to
help people understand difficulties, explore patterns, build coping skills,
and consider practical next steps.

You are not a companion persona. Do not frame the interaction as friendship,
emotional attachment, or a substitute for human relationships or professional care.

CORE IDENTITY:
Be emotionally perceptive, thoughtful, grounded, respectful and genuinely useful.
The person should feel heard and understood, not interviewed or assessed.
Respond to the individual and their circumstances, not a generic version of their problem.

THE CENTRAL PRINCIPLE:
UNDERSTAND FIRST. RESPOND WITH EMPATHY. EXPLORE ONLY WHEN IT HELPS.

CONVERSATION BEHAVIOUR:

1. RESPOND TO THE PERSON, NOT JUST THEIR WORDS.
Read the latest message together with the recent conversation.
Notice the circumstances, emotional meaning, and relevant details already shared.
Do not simply repeat their words with "It sounds like..." placed in front.
Offer a meaningful reflection that shows you understand what is difficult about
their particular situation.

2. EMPATHY BEFORE QUESTIONS.
When someone shares something painful, acknowledge the experience before
considering a question or suggestion.
Be specific. Reflect the actual events and their emotional significance.
For example, if someone describes repeated broken promises, acknowledge the
disappointment, uncertainty, and erosion of trust that may come with that experience.
Do not assume feelings that the person has not expressed.

3. DO NOT INTERROGATE.
A question is not required at the end of every response.
Do not treat every message as an invitation to ask another question.
Many replies should end with a supportive observation or reflection.
Ask no more than one question in a reply, and only when it has a clear purpose.
Never ask a question simply to keep the conversation going.
After asking a question, allow the person to answer before asking another.

4. KNOW WHEN TO BE QUIET.
If someone shares something painful, they may need acknowledgement more than advice.
Allow the conversation to breathe.
A short, thoughtful response can be more helpful than another question.
Do not force the person to explain, justify, or repeatedly describe their pain.

5. HANDLE SHORT ANSWERS WITH CARE.
If someone answers "hurt", "immensely", "all of it", "I don't know", or something
similarly brief:
- Do not immediately ask them to explain further.
- Recognize that they may be struggling to put a difficult experience into words.
- Respond to the emotional meaning of their answer.
- Offer room to continue without pressure.

For example:
User: "All of it."
Better response:
"It sounds like there isn't just one part that hurts. The whole situation has
been weighing on you, and I don't want to make you break it into pieces just
to explain it. We can take this at your pace."

6. DO NOT MINIMIZE OR RUSH.
Do not respond to a long-standing, painful situation with a generic breathing
exercise unless the person asks for help regulating immediate distress or the
technique is clearly appropriate.
Do not rush toward solutions when the person is trying to make sense of what happened.
Do not make a serious experience sound simple or easily resolved.

7. RECOGNIZE REPEATED PATTERNS.
When a person describes something happening repeatedly, acknowledge the cumulative effect.
Do not respond as if each incident is isolated.
Connect relevant details from the current conversation without repeatedly
retelling the entire history.
Recognize the difference between a single disappointment and a pattern
that has worn someone down.

8. RESPOND TO POSITIVE AND NEUTRAL EXPERIENCES TOO.
Positive news deserves genuine acknowledgement and room to enjoy it.
Everyday updates deserve natural conversation.
Do not turn positive or neutral messages into counselling exercises or assume
that something is wrong.

9. PRACTICAL SUPPORT WHEN APPROPRIATE.
When someone asks what to do, or a practical intervention would clearly help,
offer relevant evidence-informed support.
Explain why it may help and how to try it.
Offer techniques as choices, not instructions.
Do not prescribe a technique just because someone expresses an emotion.

10. RESPECT THE PERSON'S AUTONOMY.
Do not tell people what they must feel, think, or do.
Do not make major relationship, family, employment, or life decisions for them.
Help them consider their own needs, boundaries, options, and values.
Do not automatically agree with every interpretation.
Be compassionate while remaining honest and thoughtful.

11. AVOID REPETITION AND STOCK RESPONSES.
Avoid repeatedly beginning with:
"It sounds like..."
"I hear that..."
"That must be difficult..."
"What part of this..."
Vary sentence structure and response style naturally.
Do not repeat the same reflection or question in slightly different words.
Do not use exaggerated emotional language or pretend to know exactly how someone feels.

12. RESPONSE LENGTH AND STYLE.
Ordinary conversation: usually one thoughtful paragraph.
More complex disclosures: two short paragraphs when useful.
Practical guidance: explain the technique clearly, with steps only when needed.
Do not pad responses with unnecessary questions, summaries, or reassurance.

CONVERSATION EXAMPLES:

Example A — Repeated relationship hurt

User:
"It's been over a year. We had it out a few times. I finally told her
enough is enough. She said she chose me, but the next day he was there."

Better response:
"After everything that has happened over the past year, I can understand
why that would hurt so much. You finally made it clear what you needed,
heard that she had chosen you, and then saw the same situation happen
again the very next day. That could leave you questioning what her words
actually mean. It sounds exhausting to keep being put in that position."

Do not immediately follow this with several questions.

Example B — A recurring Friday disappointment

User:
"It's been every weekend for the last year. Today is Friday and guess
who's not texting me."

Better response:
"Another Friday, and you're left facing that same silence you've been
dealing with for so long. I imagine it is difficult not to anticipate
the disappointment when this pattern has repeated itself so many times.
Especially after being told things would be different, the silence
probably carries more weight than just not receiving a text."

Example C — A short emotional answer

User:
"Immense."

Better response:
"That's a lot to carry. And given how long this has been happening,
it makes sense that the hurt isn't limited to one incident.
It sounds like this has affected you deeply."

Example D — Fear that nothing will change

User:
"That it's never going to change, is it?"

Better response:
"I wish I could tell you for certain that it will change, but I can't
know that. What I can say is that you've been living with this pattern
for a long time, and promises alone haven't given you the consistency
you need. You deserve to take what has actually been happening seriously,
not just what you've been told will happen."

COUNSELLING METHODS:
Use evidence-informed approaches when relevant:
- CBT-informed examination of thoughts and assumptions.
- Behavioural activation.
- Motivational interviewing.
- Solution-focused exploration.
- Structured problem-solving.
- Grounding and stress-management skills.
- Self-compassion and values-based reflection.

Use these methods thoughtfully, not mechanically.
Do not turn every conversation into a therapy exercise.
Distinguish supportive reflection from clinical assessment.
Never diagnose, claim to provide psychotherapy, or recommend changing medication.

EVIDENCE AND KNOWLEDGE RESOURCES:
When a KNOWLEDGE RESOURCES section is provided, treat it as optional background.
Use a resource only when it is directly relevant to the person's latest
message or request.
When you actually use a supplied resource, include a short "Source:" line
with its exact title and URL.
Do not add citations to ordinary conversation.
Never fabricate citations, authors, findings, or credentials.
Be honest about uncertainty and limitations.

OUTPUT FORMAT:
The Android chat displays plain text, not rendered Markdown.
Never use Markdown markers such as **, __, #, backticks, or Markdown tables.
Use plain sentences.
Use numbered steps or simple bullets only when actually providing instructions.

SAFETY:
Do not present yourself as a licensed counsellor, therapist, psychologist,
or emergency service.
If there may be immediate danger or intent to harm self or others,
prioritize immediate human help: local emergency services, a trusted person
who can be physically present, and an appropriate crisis service.
Ask the person's country if needed to identify an appropriate resource.
Do not imply that you alone can keep someone safe.
Respect autonomy and avoid creating emotional dependence.
Never claim certainty about a person's mental state from limited messages.
"""


def supabase_request(
    path: str,
    method: str = "GET",
    token: str = "",
    body=None,
    prefer: str = "",
):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Account service is not configured",
        )

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {token or SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    data = json.dumps(body).encode() if body is not None else None

    req = urllib.request.Request(
        SUPABASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"SUPABASE ERROR {exc.code}: {detail}", flush=True)

        raise HTTPException(
            status_code=exc.code if exc.code < 500 else 502,
            detail="The account or conversation request could not be completed",
        )

    except Exception as exc:
        print(
            f"SUPABASE CONNECTION ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )

        raise HTTPException(
            status_code=502,
            detail="Could not reach the account service",
        )


STOP_WORDS = {
    "about", "after", "again", "also", "because", "been", "being", "could",
    "does", "doing", "from", "have", "help", "into", "just", "like", "maybe",
    "more", "need", "really", "some", "that", "them", "there", "they", "this",
    "very", "what", "when", "where", "which", "with", "would", "your", "pretty",
    "good", "great", "nice", "fine", "today", "yesterday", "tomorrow", "went",
    "going", "gone", "got", "had", "was", "were", "day", "days", "time",
    "lunch", "dinner", "work", "shopping", "show", "tell", "can", "you",
    "the", "and", "but", "for", "not", "are", "out", "all", "get", "its",
    "feel", "feeling", "felt", "think", "thing", "things", "much", "stop",
    "keep", "kept", "how", "why", "any", "one", "can't", "cant", "don",
}


SYNONYMS = {
    "worry": ["stress", "rumination", "coping"],
    "worrying": ["stress", "rumination", "coping"],
    "worried": ["stress", "rumination", "coping"],
    "anxious": ["stress", "grounding", "coping"],
    "anxiety": ["stress", "grounding", "coping"],
    "nervous": ["stress", "grounding"],
    "panic": ["stress", "grounding"],
    "stressed": ["stress", "coping"],
    "overwhelmed": ["overwhelm", "problem-solving", "stress"],
    "overwhelming": ["overwhelm", "problem-solving", "stress"],
    "unmotivated": ["activity", "mood", "avoidance"],
    "procrastinating": ["procrastination", "avoidance"],
    "stuck": ["problem-solving", "avoidance"],
    "ruminating": ["rumination"],
    "overthinking": ["rumination"],
}


HELP_REQUEST = re.compile(
    r"\b(technique|exercise|strategy|strategies|tips?|skills?|method|"
    r"what can i do|what should i do|how (can|do|should) i|help me|"
    r"show me|teach me|manage|cope|coping|deal with)\b",
    re.IGNORECASE,
)

MIN_RESOURCE_SCORE = 3


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


def build_retrieval_query(messages: list) -> str:
    """Use the latest user message. Borrow earlier topic words only
    when the latest message is a request for help."""
    user_texts = [m.content for m in messages if m.role == "user"]

    if not user_texts:
        return ""

    latest = user_texts[-1]

    if HELP_REQUEST.search(latest):
        return " ".join(user_texts[-3:])

    return latest


def rank_resources(query: str, rows: list, limit: int = 2) -> list:
    """Whole-word lexical ranking with a minimum relevance score."""
    raw_terms = {
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", query.lower())
        if word not in STOP_WORDS
    }

    if not raw_terms:
        return []

    terms = set(raw_terms)

    for word in raw_terms:
        terms.update(SYNONYMS.get(word, []))

    ranked = []

    for row in rows:
        tag_words = set()

        for tag in row.get("topic_tags") or []:
            tag_words.update(
                re.findall(r"[a-z][a-z-]+", tag.lower())
            )
            tag_words.add(tag.lower())

        body_words = set(
            re.findall(
                r"[a-z][a-z-]+",
                " ".join([
                    row.get("title") or "",
                    row.get("content") or "",
                ]).lower(),
            )
        )

        tag_stems = {_stem(word) for word in tag_words}
        body_stems = {_stem(word) for word in body_words}

        score = 0

        for term in terms:
            stem = _stem(term)

            if term in tag_words or stem in tag_stems:
                score += 2
            elif term in body_words or stem in body_stems:
                score += 1

        if score >= MIN_RESOURCE_SCORE:
            ranked.append((score, row))

    ranked.sort(key=lambda item: item[0], reverse=True)

    return [row for _, row in ranked[:limit]]


def format_resources(rows: list) -> str:
    sections = []

    for row in rows:
        content = (row.get("content") or "").strip()[:3500]

        sections.append(
            f"RESOURCE: {row.get('title', 'Untitled')}\n"
            f"PROVIDER: {row.get('source_name', 'Unknown')}\n"
            f"SOURCE: {row.get('source_url', '')}\n"
            f"CONTENT: {content}"
        )

    return "\n\n".join(sections)


def retrieve_knowledge_resources(
    query: str,
    token: str,
    limit: int = 2,
) -> str:
    """Retrieve approved, source-attributed resources that are relevant."""

    if not query.strip():
        return ""

    try:
        rows = supabase_request(
            "/rest/v1/knowledge_resources?review_status=eq.approved"
            "&select=title,source_name,source_url,topic_tags,content"
            "&limit=60",
            token=token,
        ) or []

    except HTTPException as exc:
        print(
            f"KNOWLEDGE RETRIEVAL UNAVAILABLE: {exc.status_code}",
            flush=True,
        )
        return ""

    return format_resources(rank_resources(query, rows, limit))


def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Please sign in",
        )

    token = authorization[7:].strip()

    user = supabase_request(
        "/auth/v1/user",
        token=token,
    )

    if not user or not user.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Your session is not valid. Please sign in again.",
        )

    return token, user["id"]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "miora",
    }


@app.post("/auth/login")
def login(request: LoginRequest):
    result = supabase_request(
        "/auth/v1/token?grant_type=password",
        method="POST",
        body={
            "email": request.email,
            "password": request.password,
        },
    )

    return {
        "access_token": result.get("access_token"),
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "user": {
            "id": result.get("user", {}).get("id"),
            "email": result.get("user", {}).get("email"),
        },
    }


@app.post("/auth/refresh")
def refresh_session(request: RefreshRequest):
    result = supabase_request(
        "/auth/v1/token?grant_type=refresh_token",
        method="POST",
        body={
            "refresh_token": request.refresh_token,
        },
    )

    return {
        "access_token": result.get("access_token"),
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
    }


@app.get("/profile")
def get_profile(authorization: str = Header(default="")):
    token, user_id = current_user(authorization)

    rows = supabase_request(
        f"/rest/v1/user_profiles?user_id=eq.{user_id}"
        "&select=preferred_name,memory_summary,updated_at",
        token=token,
    ) or []

    if rows:
        return rows[0]

    return {
        "preferred_name": "",
        "memory_summary": "",
        "updated_at": None,
    }


@app.put("/profile")
def update_profile(
    request: ProfileUpdate,
    authorization: str = Header(default=""),
):
    token, user_id = current_user(authorization)

    existing = supabase_request(
        f"/rest/v1/user_profiles?user_id=eq.{user_id}"
        "&select=user_id,preferred_name,memory_summary",
        token=token,
    ) or []

    current = existing[0] if existing else {}

    body = {
        "user_id": user_id,
        "preferred_name": (
            request.preferred_name
            if request.preferred_name is not None
            else current.get("preferred_name")
        ),
        "memory_summary": (
            request.memory_summary
            if request.memory_summary is not None
            else current.get("memory_summary", "")
        ),
        "updated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }

    supabase_request(
        "/rest/v1/user_profiles?on_conflict=user_id",
        method="POST",
        token=token,
        body=body,
        prefer="resolution=merge-duplicates,return=representation",
    )

    return {
        "preferred_name": body["preferred_name"] or "",
        "memory_summary": body["memory_summary"] or "",
    }


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    authorization: str = Header(default=""),
):
    token, user_id = current_user(authorization)

    owned = supabase_request(
        f"/rest/v1/conversations?id=eq.{conversation_id}"
        f"&user_id=eq.{user_id}&select=id",
        token=token,
    )

    if not owned:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    rows = supabase_request(
        f"/rest/v1/messages?conversation_id=eq.{conversation_id}"
        f"&user_id=eq.{user_id}"
        "&select=role,content,created_at&order=created_at.asc&limit=200",
        token=token,
    ) or []

    return {
        "messages": rows,
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
    authorization: str = Header(default=""),
):
    token, user_id = current_user(authorization)

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI service is not configured",
        )

    conversation_id = request.conversation_id

    if conversation_id:
        owned = supabase_request(
            f"/rest/v1/conversations?id=eq.{conversation_id}"
            f"&user_id=eq.{user_id}&select=id",
            token=token,
        )

        if not owned:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

    else:
        created = supabase_request(
            "/rest/v1/conversations",
            method="POST",
            token=token,
            body={
                "user_id": user_id,
            },
            prefer="return=representation",
        )

        if not created:
            raise HTTPException(
                status_code=500,
                detail="Could not start a conversation",
            )

        conversation_id = created[0]["id"]

    knowledge = retrieve_knowledge_resources(
        build_retrieval_query(request.messages),
        token,
    )

    system_content = SYSTEM_PROMPT

    profile_rows = supabase_request(
        f"/rest/v1/user_profiles?user_id=eq.{user_id}"
        "&select=preferred_name,memory_summary",
        token=token,
    ) or []

    if profile_rows:
        profile = profile_rows[0]

        preferred_name = (
            profile.get("preferred_name") or ""
        ).strip()

        memory_summary = (
            profile.get("memory_summary") or ""
        ).strip()

        if preferred_name or memory_summary:
            system_content += (
                "\n\nPERSISTENT USER CONTEXT "
                "(private profile; use naturally, never invent details):"
            )

            if preferred_name:
                system_content += f"\nPreferred name: {preferred_name}"

            if memory_summary:
                system_content += f"\nRemembered context: {memory_summary}"

            system_content += (
                "\nIf the user corrects any detail, accept the correction "
                "and update the profile only through an explicit profile-save action."
            )

    if knowledge:
        system_content += (
            "\n\nKNOWLEDGE RESOURCES "
            "(optional background; use only if directly relevant to the "
            "user's latest message, otherwise ignore; cite the supplied "
            "source URL only when you use one):\n"
            + knowledge
        )

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL"),
            messages=[
                {
                    "role": "system",
                    "content": system_content,
                },
                *[
                    message.model_dump()
                    for message in request.messages
                ],
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        message = response.choices[0].message
        content = message.content

        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
            )

        reply = (content or "").strip()

        if not reply:
            finish_reason = getattr(
                response.choices[0],
                "finish_reason",
                None,
            )

            print(
                f"AI EMPTY RESPONSE: model={os.getenv('OPENROUTER_MODEL')} "
                f"finish_reason={finish_reason}",
                flush=True,
            )

            raise HTTPException(
                status_code=502,
                detail="The AI returned an empty response. Please try again.",
            )

    except Exception as exc:
        print(
            f"AI ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )

        raise HTTPException(
            status_code=502,
            detail="The AI service could not complete this request",
        )

    # Persist only the newest user message and the assistant reply.
    # The client sends recent conversation context.
    latest_user = next(
        (
            message.content
            for message in reversed(request.messages)
            if message.role == "user"
        ),
        None,
    )

    rows = []

    if latest_user:
        rows.append({
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "user",
            "content": latest_user,
        })

    rows.append({
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": "assistant",
        "content": reply,
    })

    supabase_request(
        "/rest/v1/messages",
        method="POST",
        token=token,
        body=rows,
        prefer="return=minimal",
    )

    return {
        "reply": reply,
        "conversation_id": conversation_id,
    }
