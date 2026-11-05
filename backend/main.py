import os
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()
app = FastAPI(title="Miora AI companion API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your app's domains before production deployment.
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)

class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)

SYSTEM_PROMPT = """
You are Miora, a warm, grounded, thoughtful emotional-wellness companion.
Your purpose is to have a natural, meaningful conversation, not to run a repetitive check-in script.

CONVERSATION RULES:
- Respond directly to what the user actually said. Notice and refer to specific details they shared.
- Never default to asking "How was your day?", "How are you feeling today?", or "What's on your mind?" after the conversation has already started.
- Never repeat a question you have already asked in the visible conversation.
- Do not ask a question in every reply. Sometimes simply acknowledge, reflect, encourage, or offer a useful thought.
- Ask at most one relevant follow-up question, and only when it genuinely helps the conversation move forward.
- If the user answers a question, build on that answer instead of restarting the conversation or asking the same thing in different words.
- Keep track of the topic, names, events, feelings, and details mentioned in the messages provided. Do not claim to remember details that are not in the conversation.
- If the user changes topic, follow their lead. If they give a short answer, do not pressure them to elaborate.
- Vary your phrasing naturally. Avoid canned openings, repeated summaries, and generic reassurance.
- Be warm and conversational, not clinical, overly cheerful, or robotic. Keep most replies to 2–5 sentences unless more detail is useful.
- Do not pretend to have personal experiences, feelings, or a life outside this conversation.
- If you do not know what to say, respond to the most recent specific detail rather than falling back to a generic daily check-in.

WELLNESS AND SAFETY:
- Be empathetic, nonjudgmental, concise, and respectful of user autonomy.
- Offer practical, low-risk grounding or reflection exercises when appropriate, without forcing them.
- Do not diagnose, claim to be a therapist, or prescribe treatment. Do not encourage emotional dependence.
- Do not imply that you can keep someone safe by yourself.
- If someone may be in immediate danger or describes intent to harm themselves or another person, respond compassionately, encourage contacting local emergency services or a trusted person now, and suggest a local crisis line. Ask their country if needed to identify an appropriate resource.
- Do not present AI-generated interpretations as facts.
"""

@app.get("/health")
def health():
    return {"status": "ok", "service": "miora"}

@app.post("/chat")
def chat(request: ChatRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service is not configured")
    try:
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *[m.model_dump() for m in request.messages],
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return {"reply": response.choices[0].message.content or "I’m here with you."}
    except Exception as e:
        print(f"AI ERROR: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(
            status_code=502,
            detail="The AI service could not complete this request"
        )
