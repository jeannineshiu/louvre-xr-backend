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
from pydantic import BaseModel

from rag_engine import RAGEngine
import qa_pipeline

# RAGEngine singleton — loaded once at startup, shared across requests
_rag: RAGEngine | None = None


# ---------------------------------------------------------------------------
# Request / response schema
# ---------------------------------------------------------------------------

class AskStateInput(BaseModel):
    crowd:         str   = "low"   # "low" | "crowded"
    noise:         str   = "quiet" # "quiet" | "noisy"
    gaze_duration: float = 0.0     # seconds the visitor has been looking at the exhibit


class AskRequest(BaseModel):
    question:     str
    image_base64: str | None = None   # base64 JPEG/PNG from camera; omit to skip recognition
    state:        AskStateInput = AskStateInput()


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
    Full QA pipeline endpoint for Unity.

    Unity sends the visitor's question, an optional camera frame (base64),
    and the current sensor state. Returns the response mode, text answer,
    and the identified exhibit name.
    """
    if _rag is None:
        raise HTTPException(status_code=503, detail="RAG engine not ready yet")

    result = qa_pipeline.run(
        question=req.question,
        image_b64=req.image_base64,
        api_state=req.state.model_dump(),
        rag=_rag,
    )

    return AskResponse(
        mode=result["mode"],
        answer=result["answer"],
        exhibit=result["exhibit"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
