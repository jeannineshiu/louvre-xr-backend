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
from context_router import route


def _b64_to_frame(image_b64: str) -> np.ndarray | None:
    """Decode a base64 image string to a BGR numpy array. Returns None on failure."""
    try:
        img_bytes = base64.b64decode(image_b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def run(
    question:  str,
    image_b64: str | None,
    api_state: dict,
    rag:       RAGEngine,
) -> dict:
    """
    Full QA pipeline. No hardware access — everything is passed in.

    Args:
        question:  Visitor's natural-language question.
        image_b64: Base64-encoded JPEG/PNG of the current camera frame.
                   Pass None or "" to skip exhibit recognition.
        api_state: Flat state dict from Unity: {"crowd": str, "noise": str, "gaze_duration": float}
        rag:       Pre-loaded RAGEngine singleton (injected by server.py).

    Returns:
        {
            "mode":    str,  # NO_RESPONSE | BRIEF_TEXT | GLANCE_CARD | FULL_VOICE | BRIEF_TEXT_PROMPT
            "answer":  str,  # empty string for NO_RESPONSE
            "exhibit": str,  # recognised exhibit name or ""
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

    # Step 3: Route → mode + answer
    decision = route(question=enriched_question, rag=rag, state=api_state)

    return {
        "mode":    decision.mode,
        "answer":  decision.answer,
        "exhibit": exhibit_name,
    }


# ---------------------------------------------------------------------------
# Standalone smoke test (no Unity needed)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading RAG engine...")
    rag = RAGEngine()

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
            question="Tell me about this painting",
            image_b64=None,
            api_state=tc["state"],
            rag=rag,
        )
        print(f"\n{tc['label']}")
        print(f"  Mode   : {result['mode']}")
        print(f"  Answer : {result['answer'][:80]}{'…' if len(result['answer']) > 80 else ''}")
        print(f"  Exhibit: {result['exhibit'] or '(none)'}")
