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
from pathlib import Path
from typing import Literal

import sentry_sdk
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, field_validator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import openai_compat
import qa_pipeline
import transcription
from cache import TTLCache
from exhibits_data import EXHIBITS
from logging_config import configure_logging
from navigation_routes import EXHIBIT_NAMES, ROUTES
from rag_engine import RAGEngine
from rate_limit import (
    ASK_RATE_LIMIT,
    SESSION_RATE_LIMIT,
    TRANSCRIBE_RATE_LIMIT,
    limiter,
)
from splat_registry import list_mapping, resolve_splat
from tts import generate_sophie_audio

# Error tracking — no-ops entirely if SENTRY_DSN isn't set, so local dev and
# any deploy that hasn't configured Sentry yet behave exactly as before.
# send_default_pii=False matches this app's existing choice (see /ask below)
# not to send visitor question/answer text anywhere — Sentry gets the
# exception + traceback, not the conversation content.
_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN:
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )

configure_logging()
logger = logging.getLogger(__name__)
logger.info("sentry_enabled" if _SENTRY_DSN else "sentry_disabled_no_dsn")

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

    @field_validator("image_base64")
    @classmethod
    def image_base64_not_blank(cls, v: str | None) -> str | None:
        # Omitting the key entirely is a supported, intentional flow (text-only
        # follow-ups, navigation, chitchat — see qa_pipeline.run). Sending the key
        # with an empty value is different: it almost always means the client
        # meant to attach a camera frame and the capture silently produced
        # nothing. That used to fall through as "no image" and quietly skip
        # recognition, which is invisible to debug; surface it instead.
        if v is not None and not v.strip():
            raise ValueError(
                "image_base64 was sent but is empty — omit the field entirely to "
                "ask a text-only question, or send a non-empty base64 JPEG/PNG"
            )
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

# Rate limiting — the Limiter itself and the reasoning behind the limits live in
# rate_limit.py, shared with the OpenAI-compatible router so both surfaces count
# against the same buckets.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# OpenAI-compatible /v1 layer for third-party chat clients (see openai_compat.py).
# Off unless PARTNER_API_KEY is set; the routes exist either way so a
# misconfigured deploy answers 503 with a reason instead of a bare 404.
openai_compat.set_rag_provider(lambda: _rag)
openai_compat.register_error_handler(app)
app.include_router(openai_compat.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Flatten FastAPI's default 422 body into a single readable sentence.

    By default `detail` is a list of dicts. Debug consoles that expect a string
    — the Rokid Craft panel, and demo.html's `err.detail || HTTP ${status}` —
    render that as "[object Object]" or nothing at all, so a plain missing field
    looks like an unexplained failure. Emit a human-readable `detail` naming
    every offending field, and keep the original structured list under `errors`
    for anything that wants to parse it.
    """
    parts = []
    for err in exc.errors():
        # Drop the leading "body"/"query" segment — the field path is what the
        # caller needs, and `loc` can be empty for whole-body errors.
        loc = ".".join(str(x) for x in err.get("loc", ())[1:]) or "request body"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(parts) or "Invalid request", "errors": jsonable_encoder(exc.errors())},
    )

# Explicit allow-list — the production WebXR front end, the Rokid AI Glasses
# runtime, plus local dev origins. Using explicit origins (not "*") so the
# surface stays scoped to front ends we actually ship.
ALLOWED_ORIGINS = [
    "https://webxr-worldmodels.vercel.app",  # production front end
    "https://js.rokid.com",                  # Rokid Craft IDE / AIUI simulator
    "http://localhost:3000",                 # local dev (Next.js / Vite default)
    "http://localhost:5173",
    "https://localhost:8081",                # local dev (HTTPS, e.g. WebXR dev server)
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Starlette matches `allow_origins` by exact string only — a "https://*.rokid.com"
# entry would never match anything. Subdomain wildcards have to go through
# `allow_origin_regex`, which is applied with re.fullmatch. This covers
# js.rokid.com as well as whatever host the on-glasses runtime reports.
ALLOWED_ORIGIN_REGEX = r"https://([a-z0-9-]+\.)*rokid\.com"

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    # No cookies or Authorization-bearing sessions are used by any front end;
    # keeping this False also means a misconfigured origin can never read a
    # credentialed response.
    allow_credentials=False,
    # GET is kept alongside POST because demo.html and the WebXR front end call
    # GET /navigate, /splats and /audio/{id} cross-origin. OPTIONS is the
    # preflight itself.
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/ask", response_model=AskResponse)
@limiter.limit(ASK_RATE_LIMIT)
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
@limiter.limit(TRANSCRIBE_RATE_LIMIT)
async def transcribe(request: Request, file: UploadFile = File(...)):
    """
    Speech-to-text for multiplayer VR voice questions and demo.html's mic input.

    The front end records audio via MediaRecorder (webm or mp4) and posts it here
    as multipart/form-data. The audio is sent straight to OpenAI Whisper.

    On any failure we return {"text": ""} (HTTP 200) rather than a 500, so the
    caller can degrade gracefully instead of surfacing an error to the visitor.
    """
    try:
        text = transcription.transcribe(file.filename or "audio.webm", await file.read())
        return TranscribeResponse(text=text)
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
@limiter.limit(SESSION_RATE_LIMIT)
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
@limiter.limit("5/hour")
def tts_debug(request: Request):
    """Test OpenAI TTS connection and report status."""
    import os

    from tts import SOPHIE_VOICE, generate_sophie_audio
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
