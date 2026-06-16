"""
ContextAR - QA Pipeline
Orchestrates the pipeline in order:

  exhibit_recognizer  →  identify exhibit from camera frame
  rag_engine          →  retrieve exhibit knowledge
  context_router      →  decide mode + generate answer

The RAGEngine instance is injected by the caller (server.py) so the
FAISS index is only loaded once at startup.

Usage (standalone test):
    python qa_pipeline.py
"""

import base64
import numpy as np
import cv2

from exhibit_recognizer import recognize_exhibit
from rag_engine import RAGEngine
from context_router import route, MODE_MAX_LENGTH


def _b64_to_frame(image_b64: str) -> np.ndarray | None:
    """Decode a base64 image string to a BGR numpy array. Returns None on failure."""
    try:
        img_bytes = base64.b64decode(image_b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — any decode failure should silently return None
        return None


DEFAULT_MODE = "FULL_VOICE"


def run(
    question:  str,
    image_b64: str | None,
    rag:       RAGEngine,
    api_state: dict | None  = None,
    mode:      str | None   = None,
    history:   list[dict] | None = None,
) -> dict:
    """
    Full QA pipeline. No hardware access — everything is passed in.

    Mode selection priority:
      1. mode is set   → use it directly (skip context router)
      2. api_state set → context router decides the mode
      3. neither       → default to FULL_VOICE

    Args:
        question:  Visitor's natural-language question.
        image_b64: Base64-encoded JPEG/PNG from camera. None to skip recognition.
        rag:       Pre-loaded RAGEngine singleton (injected by server.py).
        api_state: Unity sensor state: {"crowd": str, "noise": str, "gaze_duration": float}
        mode:      Direct mode override.
                   One of: GLANCE_CARD | BRIEF_TEXT | FULL_VOICE | BRIEF_TEXT_PROMPT

    Returns:
        {
            "mode":    str,
            "answer":  str,
            "exhibit": str,
        }
    """
    # Step 1: Identify exhibit from camera frame (optional)
    exhibit_name = ""
    if image_b64:
        frame = _b64_to_frame(image_b64)
        if frame is not None:
            recognition = recognize_exhibit(frame)
            if (
                "error" not in recognition
                and recognition.get("confidence") in ("high", "medium")
                and recognition.get("name", "unknown").lower() != "unknown"
            ):
                exhibit_name = recognition["name"]

    # Step 2: Enrich question with exhibit context if recognised
    enriched_question = (
        f"[Regarding: {exhibit_name}] {question}" if exhibit_name else question
    )

    # Step 3: Decide mode and generate answer
    if mode:
        # Direct override — skip context router entirely
        max_len = MODE_MAX_LENGTH.get(mode)
        rag_result = rag.query(enriched_question, mode=mode, max_length=max_len, history=history)
        return {
            "mode":    mode,
            "answer":  rag_result["answer"],
            "exhibit": exhibit_name,
        }

    if api_state:
        # Full Unity flow — context router decides
        decision = route(question=enriched_question, rag=rag, state=api_state, history=history)
        return {
            "mode":    decision.mode,
            "answer":  decision.answer,
            "exhibit": exhibit_name,
        }

    # Fallback — no state, no mode: give a full answer
    rag_result = rag.query(enriched_question, mode=DEFAULT_MODE, history=history)
    return {
        "mode":    DEFAULT_MODE,
        "answer":  rag_result["answer"],
        "exhibit": exhibit_name,
    }


# ---------------------------------------------------------------------------
# Standalone smoke test (no Unity needed)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading RAG engine...")
    _rag = RAGEngine()

    test_cases = [
        {
            "label": "Passing by — NO_RESPONSE",
            "state": {"crowd": "low",     "noise": "quiet", "gaze_duration": 2.0},
        },
        {
            "label": "Glancing, low crowd — BRIEF_TEXT",
            "state": {"crowd": "low",     "noise": "noisy", "gaze_duration": 8.0},
        },
        {
            "label": "Glancing, crowded — GLANCE_CARD",
            "state": {"crowd": "crowded", "noise": "quiet", "gaze_duration": 10.0},
        },
        {
            "label": "Engaged, low crowd — FULL_VOICE",
            "state": {"crowd": "low",     "noise": "quiet", "gaze_duration": 20.0},
        },
        {
            "label": "Engaged, crowded — BRIEF_TEXT_PROMPT",
            "state": {"crowd": "crowded", "noise": "noisy", "gaze_duration": 20.0},
        },
    ]

    for tc in test_cases:
        result = run(
            question="Tell me about this sculpture",
            image_b64=None,
            api_state=tc["state"],
            rag=_rag,
        )
        print(f"\n{tc['label']}")
        print(f"  Mode   : {result['mode']}")
        print(f"  Answer : {result['answer'][:80]}{'…' if len(result['answer']) > 80 else ''}")
        print(f"  Exhibit: {result['exhibit'] or '(none)'}")
