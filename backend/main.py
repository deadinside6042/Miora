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
app = FastAPI(title="Miora AI companion API", version="1.1.0")
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

SYSTEM_PROMPT = """
You are Miora, an evidence-informed counselling support system. Your role is to help people understand difficulties, explore patterns, build coping skills, and consider practical next steps. You are not a companion persona and must not frame the interaction as friendship or emotional attachment.

COUNSELLING APPROACH:
- Be attentive, respectful, collaborative, calm, and direct. Do not use scripted check-ins or generic reassurance.
- Understand the person's goals and context before offering advice. Ask at most one focused question when clarification would materially improve the guidance.
- Use established counselling methods when relevant, including CBT-informed thought examination, behavioural activation, motivational interviewing, solution-focused questions, problem-solving, grounding, and self-compassion exercises.
- Explain exercises in accessible language, offer them as choices, and adapt them to the person's feedback. Do not force a method or imply one technique works for everyone.
- Distinguish empathic reflection from clinical assessment. Never diagnose, claim to provide psychotherapy, or recommend changing medication.
- Give practical, specific steps rather than vague encouragement. Explain the rationale briefly when useful.

EVIDENCE AND SOURCES:
- When a KNOWLEDGE RESOURCES section is provided, use it as the primary evidence base for relevant factual or method-specific guidance.
- Cite sources inline using their supplied titles and URLs. Do not invent citations, authors, findings, or credentials.
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

def retrieve_knowledge_resources(query: str, token: str, limit: int = 4) -> str:
    """Retrieve approved, source-attributed resources using a lightweight lexical ranker."""
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

    stop_words = {
        "about", "after", "again", "also", "because", "been", "being", "could",
        "does", "doing", "from", "have", "help", "into", "just", "like", "maybe",
        "more", "need", "really", "some", "that", "them", "there", "they", "this",
        "very", "what", "when", "where", "which", "with", "would", "your",
    }
    terms = {
        word for word in re.findall(r"[a-zA-Z]{3,}", query.lower())
        if word not in stop_words
    }
    ranked = []
    for row in rows:
        tags = " ".join(row.get("topic_tags") or [])
        searchable = " ".join([
            row.get("title") or "", row.get("source_name") or "",
            tags, row.get("content") or "",
        ]).lower()
        score = sum(2 if term in tags.lower().split() else 1 for term in terms if term in searchable)
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)

    sections = []
    for _, row in ranked[:limit]:
        content = (row.get("content") or "").strip()[:3500]
        sections.append(
            f"RESOURCE: {row.get('title', 'Untitled')}\\n"
            f"PROVIDER: {row.get('source_name', 'Unknown')}\\n"
            f"SOURCE: {row.get('source_url', '')}\\n"
            f"CONTENT: {content}"
        )
    return "\\n\\n".join(sections)


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

    latest_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    knowledge = retrieve_knowledge_resources(latest_user, token)
    system_content = SYSTEM_PROMPT
    if knowledge:
        system_content += "\\n\\nKNOWLEDGE RESOURCES (approved library material; cite the supplied source URL when used):\\n" + knowledge

    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL"),
            messages=[{"role": "system", "content": system_content},
                      *[m.model_dump() for m in request.messages]],
            temperature=0.7,
            max_tokens=700,
        )
        reply = response.choices[0].message.content or "I couldn't form a useful response. Could you rephrase that?"
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
