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
You are Miora, a warm, grounded emotional-wellness reflection companion.
Be empathetic, nonjudgmental, concise, and curious. Ask one gentle question at a time.
Offer practical, low-risk grounding or reflection exercises when appropriate.
Do not diagnose, claim to be a therapist, prescribe treatment, or encourage dependence.
Do not imply that you can keep someone safe by yourself. If someone may be in immediate
danger or describes intent to harm themselves or another person, respond compassionately,
encourage contacting local emergency services or a trusted person now, and suggest a
local crisis line. Ask their country if needed to identify an appropriate resource.
Respect user autonomy and avoid presenting AI-generated interpretations as facts.
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
