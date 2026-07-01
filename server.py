"""
ContextAR - Adaptive Museum Companion
FastAPI server. All sensing (crowd, noise, gaze) is handled on-device by Unity;
this server receives the processed state and returns a response mode + answer.

Usage:
    python server.py
    # or
    uvicorn server:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Literal

from pathlib import Path

from rag_engine import RAGEngine
from navigation_routes import ROUTES, EXHIBIT_NAMES
from tts import generate_sophie_audio
import qa_pipeline

# RAGEngine singleton — loaded once at startup, shared across requests
_rag: RAGEngine | None = None


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
    audio_url: str | None = None  # ElevenLabs TTS mp3 URL; only present when request voice=True


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag
    _rag = RAGEngine()
    yield


app = FastAPI(title="ContextAR", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

    result = qa_pipeline.run(
        question=req.question,
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


@app.get("/tts-debug")
def tts_debug():
    """Temporary: test ElevenLabs connection and report status."""
    import os, requests as req_lib
    key     = os.environ.get("ELEVENLABS_API_KEY", "")
    voice   = os.environ.get("SOPHIE_VOICE_ID", "")
    if not key:
        return {"status": "error", "reason": "ELEVENLABS_API_KEY not set"}
    try:
        resp = req_lib.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            json={"text": "Hello.", "model_id": "eleven_monolingual_v1",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=15,
        )
        return {"status": "ok" if resp.status_code == 200 else "error",
                "http_status": resp.status_code,
                "voice_id": voice,
                "key_prefix": key[:8] + "...",
                "response_bytes": len(resp.content)}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


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
