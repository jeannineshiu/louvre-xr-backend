"""
ContextAR - Adaptive Museum Companion
FastAPI server. All sensing (crowd, noise, gaze) is handled on-device by Unity;
this server receives the processed state and returns a response mode + answer.

Usage:
    python server.py
    # or
    uvicorn server:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Literal

from pathlib import Path

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from rag_engine import RAGEngine
from navigation_routes import ROUTES, EXHIBIT_NAMES
from tts import generate_sophie_audio
import qa_pipeline

# RAGEngine singleton — loaded once at startup, shared across requests
_rag: RAGEngine | None = None

# OpenAI client singleton — lazily created, reused across requests (Whisper transcription)
_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai_client


# ---------------------------------------------------------------------------
# Request / response schema
# ---------------------------------------------------------------------------

VALID_MODES = {"GLANCE_CARD", "BRIEF_TEXT", "FULL_VOICE", "BRIEF_TEXT_PROMPT", "NAVIGATION", "SHOP"}


class AskStateInput(BaseModel):
    crowd:         str   = "low"   # "low" | "crowded"
    noise:         str   = "quiet" # "quiet" | "noisy"
    gaze_duration: float = 0.0     # seconds the visitor has been looking at the exhibit


class HistoryMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question:     str
    image_base64: str | None              = None  # base64 JPEG/PNG from camera; omit to skip recognition
    state:        AskStateInput | None    = None  # omit to skip context routing
    mode:         str | None             = None  # GLANCE_CARD | BRIEF_TEXT | FULL_VOICE | BRIEF_TEXT_PROMPT
    history:      list[HistoryMessage] | None = None  # prior turns: [{role, content}, ...]
    voice:        bool                   = False  # if True, generate ElevenLabs TTS and return audio_url
    # Multiplayer room context — lets Sophie address the group / the asker
    asker_name:   str | None             = None  # who is asking, e.g. "Alice"
    participants: list[str] | None       = None  # everyone in the room, e.g. ["Alice", "Bob", "Charlie"]

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty or whitespace")
        return v


class AskResponse(BaseModel):
    mode:      str        # NO_RESPONSE | BRIEF_TEXT | GLANCE_CARD | FULL_VOICE | BRIEF_TEXT_PROMPT
    answer:    str        # text answer; empty for NO_RESPONSE
    exhibit:   str        # recognised exhibit name; empty if not identified
    audio_url: str | None = None  # TTS mp3 URL; only present when request voice=True


class SessionStartRequest(BaseModel):
    exhibit: str | None = None  # exhibit name if already identified; omit for generic welcome
    voice:   bool = False       # if True, generate TTS audio and return audio_url


class SessionStartResponse(BaseModel):
    greeting:  str
    audio_url: str | None = None


class TranscribeResponse(BaseModel):
    text: str  # transcribed speech; empty string on failure


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag
    _rag = RAGEngine()
    yield


app = FastAPI(title="ContextAR", version="0.2.0", lifespan=lifespan)

# Explicit allow-list — the production WebXR front end plus local dev origins.
# Using explicit origins (not "*") so credentialed requests keep working.
ALLOWED_ORIGINS = [
    "https://webxr-worldmodels.vercel.app",  # production front end
    "http://localhost:3000",                 # local dev (Next.js / Vite default)
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request):
    """
    QA endpoint. Three usage patterns:

    1. Simplest — no state, no mode (default FULL_VOICE):
       { "question": "Who made this?" }

    2. Direct mode — skip context routing:
       { "question": "Who made this?", "mode": "GLANCE_CARD" }

    3. Full Unity flow — context router decides mode:
       { "question": "...", "state": { "crowd": "low", "noise": "quiet", "gaze_duration": 20.0 } }
    """
    if _rag is None:
        raise HTTPException(status_code=503, detail="RAG engine not ready yet")

    if req.mode and req.mode not in VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{req.mode}'. Choose from: {sorted(VALID_MODES)}",
        )

    # Multiplayer room context — prepend so Sophie can address the group and the asker
    question = req.question
    if req.participants and req.asker_name:
        names = ", ".join(req.participants)
        count = len(req.participants)
        person = "person" if count == 1 else "people"
        question = (
            f"[Room context: {count} {person} in this room — {names}. "
            f"This question is from {req.asker_name}.]\n"
            f"Question: {req.question}"
        )

    result = qa_pipeline.run(
        question=question,
        image_b64=req.image_base64,
        api_state=req.state.model_dump() if req.state else None,
        mode=req.mode,
        rag=_rag,
        history=[m.model_dump() for m in req.history] if req.history else None,
    )

    # Optional ElevenLabs TTS — only when voice=True and there is an answer
    audio_url: str | None = None
    if req.voice and result["answer"]:
        file_id = generate_sophie_audio(result["answer"])
        if file_id:
            base = str(request.base_url).rstrip("/")
            audio_url = f"{base}/audio/{file_id}"

    return AskResponse(
        mode=result["mode"],
        answer=result["answer"],
        exhibit=result["exhibit"],
        audio_url=audio_url,
    )


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    """
    Speech-to-text for multiplayer VR voice questions.

    The front end records audio via MediaRecorder (webm or mp4) and posts it here
    as multipart/form-data. The audio is sent straight to OpenAI Whisper.

    On any failure we return {"text": ""} (HTTP 200) rather than a 500, so the
    caller can degrade gracefully instead of surfacing an error to the visitor.
    """
    try:
        content = await file.read()
        if not content:
            return TranscribeResponse(text="")
        result = _get_openai_client().audio.transcriptions.create(
            model="whisper-1",
            file=(file.filename or "audio.webm", content),
        )
        return TranscribeResponse(text=(result.text or "").strip())
    except Exception:  # noqa: BLE001 — degrade to empty text instead of 500
        return TranscribeResponse(text="")


@app.get("/navigate")
def navigate(from_exhibit: str, to_exhibit: str):
    """Direct route lookup — no FAISS, no LLM."""
    if from_exhibit == to_exhibit:
        name = EXHIBIT_NAMES.get(from_exhibit, from_exhibit)
        return {"found": True, "directions": f"You are already at {name}."}
    key = (from_exhibit, to_exhibit)
    directions = ROUTES.get(key)
    if not directions:
        return {"found": False, "directions": ""}
    return {
        "found":      True,
        "directions": directions,
        "from_name":  EXHIBIT_NAMES.get(from_exhibit, from_exhibit),
        "to_name":    EXHIBIT_NAMES.get(to_exhibit, to_exhibit),
    }


@app.get("/audio/{file_id}")
def audio(file_id: str):
    """Serve a generated Sophie TTS mp3 file."""
    path = Path("temp_audio") / f"{file_id}.mp3"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(path), media_type="audio/mpeg")


@app.get("/demo")
def demo():
    return FileResponse("demo.html", media_type="text/html")


@app.post("/session/start", response_model=SessionStartResponse)
def session_start(req: SessionStartRequest, request: Request):
    """
    Generate Sophie's welcome greeting when a visitor joins a multiplayer room.
    Optionally include the exhibit name if already identified.
    Pass voice=true to receive a TTS audio URL for broadcast to all room members.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0.4)

    if req.exhibit:
        prompt = (
            f"A group of visitors has just joined a shared WebXR tour room. "
            f"They are standing in front of '{req.exhibit}'. "
            f"Greet them warmly as Sophie, their MuseXR guide, in 2–3 sentences. "
            f"Welcome them, mention the sculpture by name, and invite them to ask you anything."
        )
    else:
        prompt = (
            "A group of visitors has just joined a shared WebXR tour room at the Louvre Museum. "
            "Greet them warmly as Sophie, their MuseXR guide, in 2–3 sentences. "
            "Welcome them to the experience and invite them to point their camera at any sculpture "
            "or ask you anything about the collection."
        )

    system = (
        "You are Sophie, a warm and knowledgeable museum guide for MuseXR. "
        "Speak in a friendly, personal tone. Plain text only — no markdown."
    )

    response  = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    greeting  = response.content.strip()

    audio_url: str | None = None
    if req.voice and greeting:
        file_id = generate_sophie_audio(greeting)
        if file_id:
            base      = str(request.base_url).rstrip("/")
            audio_url = f"{base}/audio/{file_id}"

    return SessionStartResponse(greeting=greeting, audio_url=audio_url)


@app.get("/tts-debug")
def tts_debug():
    """Test OpenAI TTS connection and report status."""
    import os
    from tts import generate_sophie_audio, SOPHIE_VOICE
    key   = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return {"status": "error", "reason": "OPENAI_API_KEY not set"}
    file_id = generate_sophie_audio("Hello, I am Sophie.")
    if file_id:
        return {"status": "ok", "voice": SOPHIE_VOICE,
                "file_id": file_id, "audio_url": f"/audio/{file_id}"}
    return {"status": "error", "reason": "TTS generation failed — check Railway logs"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
