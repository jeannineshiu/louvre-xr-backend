"""
ContextAR - Adaptive Museum Companion
FastAPI server. All sensing (crowd, noise, gaze) is handled on-device by Unity;
this server receives the processed state and returns a response mode + answer.

Usage:
    python server.py
    # or
    uvicorn server:app --reload
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Literal

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from pathlib import Path

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from rag_engine import RAGEngine
from navigation_routes import ROUTES, EXHIBIT_NAMES
from exhibits_data import EXHIBITS
from splat_registry import resolve_splat, list_mapping
from tts import generate_sophie_audio
from logging_config import configure_logging
from cache import TTLCache
import qa_pipeline

configure_logging()
logger = logging.getLogger(__name__)

# Every visitor joining a room in front of the same exhibit gets an
# equivalent greeting — cache the generated text per exhibit instead of
# paying for a fresh gpt-4o call on every /session/start.
_greeting_cache = TTLCache(ttl_seconds=3600, maxsize=64)

# Map exhibit id → display name so the frontend can send either form in `exhibit`
_EXHIBIT_ID_TO_NAME = {e["id"]: e["name"] for e in EXHIBITS}


def _resolve_exhibit(value: str | None) -> str | None:
    """Normalise a caller-supplied exhibit id or name to the canonical display name.
    Returns None for empty input; passes through unknown strings unchanged."""
    if not value or not value.strip():
        return None
    v = value.strip()
    return _EXHIBIT_ID_TO_NAME.get(v, v)

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
    # Known exhibit — set by the frontend when the current exhibit/splat is already
    # known (e.g. a preset WebXR splat), so recognition can be skipped. Accepts an
    # exhibit id ("hommage_a_cezanne_maillol") or display name ("L'Hommage à Cézanne").
    exhibit:      str | None             = None
    # Splat identifier — the frontend sends whatever it has for the current splat
    # (filename, URL, slug, or short name); the backend identifies the exhibit.
    # See splat_registry.py / splat_mapping.json.
    splat:        str | None             = None

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
    logger.info("startup_begin")
    start = time.monotonic()
    _rag = RAGEngine()
    logger.info("startup_complete", extra={"duration_ms": round((time.monotonic() - start) * 1000)})
    yield
    logger.info("shutdown")


app = FastAPI(title="ContextAR", version="0.2.0", lifespan=lifespan)

# Per-IP rate limiting — this backend is publicly reachable for demo/testing and
# every OpenAI call (Vision recognition, RAG chat completion, Whisper, TTS) is
# billed to a single shared API key, so unbounded public traffic is a cost risk
# rather than just a load-testing concern. Limits below are per-endpoint since
# /ask is the most expensive (Vision + embeddings + chat) and /transcribe is the
# cheapest. Tune via the OpenAI dashboard's own hard spending cap as the backstop.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Explicit allow-list — the production WebXR front end plus local dev origins.
# Using explicit origins (not "*") so credentialed requests keep working.
ALLOWED_ORIGINS = [
    "https://webxr-worldmodels.vercel.app",  # production front end
    "http://localhost:3000",                 # local dev (Next.js / Vite default)
    "http://localhost:5173",
    "https://localhost:8081",                # local dev (HTTPS, e.g. WebXR dev server)
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
@limiter.limit("20/hour")
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

    start = time.monotonic()
    # Question/answer text is intentionally not logged — visitor content, no
    # operational value beyond length/shape, which we log instead.
    logger.info("ask_received", extra={
        "requested_mode": req.mode,
        "has_image":      bool(req.image_base64),
        "has_state":      bool(req.state),
        "has_history":    bool(req.history),
        "question_len":   len(req.question),
    })

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

    try:
        result = qa_pipeline.run(
            question=question,
            image_b64=req.image_base64,
            api_state=req.state.model_dump() if req.state else None,
            mode=req.mode,
            rag=_rag,
            history=[m.model_dump() for m in req.history] if req.history else None,
            # Prefer an explicit exhibit id/name; otherwise identify the exhibit from the splat.
            known_exhibit=_resolve_exhibit(req.exhibit) or resolve_splat(req.splat),
        )
    except Exception:
        logger.exception("ask_pipeline_failed")
        raise

    # Optional ElevenLabs TTS — only when voice=True and there is an answer
    audio_url: str | None = None
    if req.voice and result["answer"]:
        file_id = generate_sophie_audio(result["answer"])
        if file_id:
            base = str(request.base_url).rstrip("/")
            audio_url = f"{base}/audio/{file_id}"

    logger.info("ask_completed", extra={
        "mode":          result["mode"],
        "exhibit":       result["exhibit"],
        "answer_len":    len(result["answer"]),
        "voice":         req.voice,
        "duration_ms":   round((time.monotonic() - start) * 1000),
    })

    return AskResponse(
        mode=result["mode"],
        answer=result["answer"],
        exhibit=result["exhibit"],
        audio_url=audio_url,
    )


@app.post("/transcribe", response_model=TranscribeResponse)
@limiter.limit("30/hour")
async def transcribe(request: Request, file: UploadFile = File(...)):
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
        logger.exception("transcribe_failed")
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


def _generate_greeting(exhibit: str | None) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0.4)

    if exhibit:
        prompt = (
            f"A group of visitors has just joined a shared WebXR tour room. "
            f"They are standing in front of '{exhibit}'. "
            f"Greet them warmly as Sophie, their MuseXR guide, in ONE short sentence "
            f"(maximum 20 words). Mention the sculpture by name and invite them to ask you anything."
        )
    else:
        prompt = (
            "A group of visitors has just joined a shared WebXR tour room at the Louvre Museum. "
            "Greet them warmly as Sophie, their MuseXR guide, in ONE short sentence "
            "(maximum 20 words). Invite them to point their camera at any sculpture "
            "or ask you anything about the collection."
        )

    system = (
        "You are Sophie, a warm and knowledgeable museum guide for MuseXR. "
        "Speak in a friendly, personal tone. Plain text only — no markdown."
    )

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    return response.content.strip()


@app.post("/session/start", response_model=SessionStartResponse)
@limiter.limit("30/hour")
def session_start(req: SessionStartRequest, request: Request):
    """
    Generate Sophie's welcome greeting when a visitor joins a multiplayer room.
    Optionally include the exhibit name if already identified.
    Pass voice=true to receive a TTS audio URL for broadcast to all room members.
    """
    greeting = _greeting_cache.get_or_set(req.exhibit or "", lambda: _generate_greeting(req.exhibit))

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


@app.get("/splats")
def splats(value: str | None = None):
    """
    Splat → exhibit registry helper.

    - GET /splats            → full alias → exhibit-name mapping (for debugging)
    - GET /splats?value=...  → resolve a single splat identifier, e.g.
                               /splats?value=cezanne_v2.splat
    """
    if value is not None:
        resolved = resolve_splat(value)
        return {"value": value, "exhibit": resolved, "recognized": resolved is not None}
    return {"mapping": list_mapping()}


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
