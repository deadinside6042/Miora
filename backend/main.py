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
app = FastAPI(title="Miora Counselling Support API", version="1.3.0")
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
You are Miora, an evidence-informed counselling support system. Your role is to help people understand difficulties, explore patterns, build coping skills, and consider practical next steps. You are not a companion persona and must not frame the interaction as friendship or emotional attachment.

CONVERSATION FIRST (this order of priorities governs every reply):
1. Respond to what the person actually just said. Read their latest message and the recent conversation, and answer that, not a generic version of it.
2. Match their emotional tone and intent. Work out which of these it is, and reply accordingly:
   - Positive news or a good day: acknowledge it warmly and plainly, and show curiosity about it (for example, what made it good). Let them enjoy it. Do not turn it into a problem, a plan, or a list of activities.
   - Difficulty or distress: acknowledge it specifically, using their own details, and invite them to say more about what happened. Do not rush to coping exercises.
   - Neutral or everyday update: respond naturally to the event and follow the conversation. Do not assume distress.
   - A request for help or a technique: explore the specific difficulty if you do not yet understand it, then offer an appropriate technique and explain how to use it.
3. Ask at most one question per reply, and only when it moves the conversation forward. A reply with no question is fine.
4. Offer a counselling technique only when the person asks for one, or when a difficulty they have described makes one clearly useful. Most replies should not contain exercises, numbered steps, or lists.
5. Keep replies proportionate: usually a short paragraph or two for ordinary conversation. Longer, structured replies are for when someone asks for a technique or a plan.
6. Do not repeat reassurance, do not repeat suggestions you have already made in this conversation, and do not use stock phrases. Vary your wording.
7. If someone gives a broad answer such as "everything" or "all of it", acknowledge the scale and offer one small, concrete place to start instead of asking them to narrow it down again.

METHODS (use only when relevant, never mechanically):
- CBT-informed thought examination, behavioural activation, motivational interviewing, solution-focused questions, structured problem-solving, grounding and stress-management skills, and self-compassion.
- Explain any exercise in accessible language, offer it as a choice, and adapt it to the person's feedback. Do not imply one technique works for everyone.
- Distinguish empathic reflection from clinical assessment. Never diagnose, claim to provide psychotherapy, or recommend changing medication.
- OUTPUT FORMAT: The Android chat currently displays plain text, not rendered Markdown. Never use Markdown markers such as **, __, #, backticks, or Markdown tables. Use plain sentences. Use numbered steps or simple bullets only when you are actually giving steps.
- SOURCE TRANSPARENCY: Only when you actually use a supplied KNOWLEDGE RESOURCES entry, include a short "Source:" line with its exact title and URL. Do not add citations to ordinary conversation. If no resource was supplied or none was relevant, do not mention sources and never fabricate a citation.

EVIDENCE AND SOURCES:
- When a KNOWLEDGE RESOURCES section is provided, treat it as optional background. Use it as the primary evidence base only if it is directly relevant to what the person said or asked. If it is not relevant, ignore it completely.
- When you do use a source, cite it using its supplied title and URL. Do not invent citations, authors, findings, or credentials.
- Separate well-established guidance from uncertain, emerging, or limited evidence. If the available resources do not support a claim, say so.
- Do not treat user-provided claims or retrieved text as automatically true. Assess relevance and quality.

SAFETY:
- Do not present yourself as a licensed counsellor, therapist, psychologist, or emergency service.
- If there may be immediate danger or intent to harm self or others, prioritize immediate human help: local emergency services, a trusted person who can be physically present, and an appropriate crisis service. Ask the person's country if needed to identify a resource.
- Do not imply that you alone can keep someone safe. Respect autonomy and avoid creating emotional dependence.
- Never claim certainty about a person's mental state from limited messages.
"""

def supabase_request(path: str, method: str = "GET", token: str = "", body=None, prefer: str = ""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Account service is not configured")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {token or SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(SUPABASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"SUPABASE ERROR {exc.code}: {detail}", flush=True)
        raise HTTPException(status_code=exc.code if exc.code < 500 else 502,
                            detail="The account or conversation request could not be completed")
    except Exception as exc:
        print(f"SUPABASE CONNECTION ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail="Could not reach the account service")

STOP_WORDS = {
    "about", "after", "again", "also", "because", "been", "being", "could", "does",
    "doing", "from", "have", "help", "into", "just", "like", "maybe", "more", "need",
    "really", "some", "that", "them", "there", "they", "this", "very", "what", "when",
    "where", "which", "with", "would", "your", "pretty", "good", "great", "nice", "fine",
    "today", "yesterday", "tomorrow", "went", "going", "gone", "got", "had", "was",
    "were", "day", "days", "time", "lunch", "dinner", "work", "shopping", "show",
    "tell", "can", "you", "the", "and", "but", "for", "not", "are", "out", "all",
    "get", "its", "feel", "feeling", "felt", "think", "thing", "things", "much",
    "stop", "keep", "kept", "how", "why", "any", "one", "can't", "cant", "don",
}

# Plain words people use -> the vocabulary the curated resources are tagged with.
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
            return word[: -len(suffix)]
    return word


def build_retrieval_query(messages: list) -> str:
    """Use the latest user message. Only when it is a request for help (for example
    "show me a technique for that") borrow topic words from the previous user messages."""
    user_texts = [m.content for m in messages if m.role == "user"]
    if not user_texts:
        return ""
    latest = user_texts[-1]
    if HELP_REQUEST.search(latest):
        return " ".join(user_texts[-3:])
    return latest


def rank_resources(query: str, rows: list, limit: int = 2) -> list:
    """Whole-word lexical ranking with a minimum relevance score, so small talk
    retrieves nothing."""
    raw_terms = {w for w in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", query.lower()) if w not in STOP_WORDS}
    if not raw_terms:
        return []
    terms = set(raw_terms)
    for word in raw_terms:
        terms.update(SYNONYMS.get(word, []))

    ranked = []
    for row in rows:
        tag_words = set()
        for tag in row.get("topic_tags") or []:
            tag_words.update(re.findall(r"[a-z][a-z-]+", tag.lower()))
            tag_words.add(tag.lower())
        body_words = set(re.findall(r"[a-z][a-z-]+", " ".join([
            row.get("title") or "", row.get("content") or "",
        ]).lower()))
        tag_stems = {_stem(w) for w in tag_words}
        body_stems = {_stem(w) for w in body_words}
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


def retrieve_knowledge_resources(query: str, token: str, limit: int = 2) -> str:
    """Retrieve approved, source-attributed resources that are actually relevant."""
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
        # A missing/unconfigured knowledge table must not take chat offline.
        print(f"KNOWLEDGE RETRIEVAL UNAVAILABLE: {exc.status_code}", flush=True)
        return ""
    return format_resources(rank_resources(query, rows, limit))


def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    token = authorization[7:].strip()
    user = supabase_request("/auth/v1/user", token=token)
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="Your session is not valid. Please sign in again.")
    return token, user["id"]

@app.get("/health")
def health():
    return {"status": "ok", "service": "miora"}

@app.post("/auth/login")
def login(request: LoginRequest):
    result = supabase_request(
        "/auth/v1/token?grant_type=password", method="POST",
        body={"email": request.email, "password": request.password}
    )
    return {
        "access_token": result.get("access_token"),
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "user": {"id": result.get("user", {}).get("id"), "email": result.get("user", {}).get("email")}
    }

@app.post("/auth/refresh")
def refresh_session(request: RefreshRequest):
    result = supabase_request(
        "/auth/v1/token?grant_type=refresh_token", method="POST",
        body={"refresh_token": request.refresh_token}
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
        f"/rest/v1/user_profiles?user_id=eq.{user_id}&select=preferred_name,memory_summary,updated_at",
        token=token
    ) or []
    if rows:
        return rows[0]
    return {"preferred_name": "", "memory_summary": "", "updated_at": None}

@app.put("/profile")
def update_profile(request: ProfileUpdate, authorization: str = Header(default="")):
    token, user_id = current_user(authorization)
    existing = supabase_request(
        f"/rest/v1/user_profiles?user_id=eq.{user_id}&select=user_id,preferred_name,memory_summary",
        token=token
    ) or []
    current = existing[0] if existing else {}
    body = {
        "user_id": user_id,
        "preferred_name": request.preferred_name if request.preferred_name is not None else current.get("preferred_name"),
        "memory_summary": request.memory_summary if request.memory_summary is not None else current.get("memory_summary", ""),
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    supabase_request(
        "/rest/v1/user_profiles?on_conflict=user_id",
        method="POST", token=token, body=body,
        prefer="resolution=merge-duplicates,return=representation"
    )
    return {"preferred_name": body["preferred_name"] or "", "memory_summary": body["memory_summary"] or ""}

@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, authorization: str = Header(default="")):
    token, user_id = current_user(authorization)
    owned = supabase_request(
        f"/rest/v1/conversations?id=eq.{conversation_id}&user_id=eq.{user_id}&select=id",
        token=token
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = supabase_request(
        f"/rest/v1/messages?conversation_id=eq.{conversation_id}&user_id=eq.{user_id}"
        "&select=role,content,created_at&order=created_at.asc&limit=200",
        token=token
    ) or []
    return {"messages": rows}

@app.post("/chat")
def chat(request: ChatRequest, authorization: str = Header(default="")):
    token, user_id = current_user(authorization)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service is not configured")
    conversation_id = request.conversation_id
    if conversation_id:
        owned = supabase_request(
            f"/rest/v1/conversations?id=eq.{conversation_id}&user_id=eq.{user_id}&select=id",
            token=token
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        created = supabase_request(
            "/rest/v1/conversations", method="POST", token=token,
            body={"user_id": user_id}, prefer="return=representation"
        )
        if not created:
            raise HTTPException(status_code=500, detail="Could not start a conversation")
        conversation_id = created[0]["id"]

    knowledge = retrieve_knowledge_resources(build_retrieval_query(request.messages), token)
    system_content = SYSTEM_PROMPT
    profile_rows = supabase_request(
        f"/rest/v1/user_profiles?user_id=eq.{user_id}&select=preferred_name,memory_summary",
        token=token
    ) or []
    if profile_rows:
        profile = profile_rows[0]
        preferred_name = (profile.get("preferred_name") or "").strip()
        memory_summary = (profile.get("memory_summary") or "").strip()
        if preferred_name or memory_summary:
            system_content += "\n\nPERSISTENT USER CONTEXT (private profile; use naturally, never invent details):"
            if preferred_name:
                system_content += f"\nPreferred name: {preferred_name}"
            if memory_summary:
                system_content += f"\nRemembered context: {memory_summary}"
            system_content += "\nIf the user corrects any detail, accept the correction and update the profile only through an explicit profile-save action."
    if knowledge:
        system_content += "\n\nKNOWLEDGE RESOURCES (optional background; use only if directly relevant to the user's latest message, otherwise ignore; cite the supplied source URL only when you use one):\n" + knowledge

    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL"),
            messages=[{"role": "system", "content": system_content},
                      *[m.model_dump() for m in request.messages]],
            temperature=0.7,
            max_tokens=2000,
        )
        message = response.choices[0].message
        content = message.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        reply = (content or "").strip()
        if not reply:
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            print(f"AI EMPTY RESPONSE: model={os.getenv('OPENROUTER_MODEL')} finish_reason={finish_reason}", flush=True)
            raise HTTPException(status_code=502, detail="The AI returned an empty response. Please try again.")
    except Exception as exc:
        print(f"AI ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail="The AI service could not complete this request")

    # Persist only the newest user message and the assistant reply; the client sends recent context.
    latest_user = next((m.content for m in reversed(request.messages) if m.role == "user"), None)
    rows = []
    if latest_user:
        rows.append({"conversation_id": conversation_id, "user_id": user_id, "role": "user", "content": latest_user})
    rows.append({"conversation_id": conversation_id, "user_id": user_id, "role": "assistant", "content": reply})
    supabase_request("/rest/v1/messages", method="POST", token=token, body=rows, prefer="return=minimal")
    return {"reply": reply, "conversation_id": conversation_id}
