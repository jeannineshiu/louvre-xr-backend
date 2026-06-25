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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Literal

from rag_engine import RAGEngine
import qa_pipeline

# RAGEngine singleton — loaded once at startup, shared across requests
_rag: RAGEngine | None = None


# ---------------------------------------------------------------------------
# Request / response schema
# ---------------------------------------------------------------------------

VALID_MODES = {"GLANCE_CARD", "BRIEF_TEXT", "FULL_VOICE", "BRIEF_TEXT_PROMPT", "NAVIGATION"}


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

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty or whitespace")
        return v


class AskResponse(BaseModel):
    mode:    str   # NO_RESPONSE | BRIEF_TEXT | GLANCE_CARD | FULL_VOICE | BRIEF_TEXT_PROMPT
    answer:  str   # text answer; empty for NO_RESPONSE
    exhibit: str   # recognised exhibit name; empty if not identified


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
def ask(req: AskRequest):
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

    return AskResponse(
        mode=result["mode"],
        answer=result["answer"],
        exhibit=result["exhibit"],
    )


@app.get("/demo")
def demo():
    return FileResponse("demo.html", media_type="text/html")


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
