"""
ContextAR - Context Router
Decides how the AR layer should respond based on gaze_duration, crowd, and noise.

Decision table:
┌───────────────┬──────────┬───────┬────────────────────┐
│ gaze_duration │ crowd    │ noise │ mode               │
├───────────────┼──────────┼───────┼────────────────────┤
│ < 5s          │ any      │ any   │ NO_RESPONSE        │
│ 5–15s         │ low      │ any   │ BRIEF_TEXT         │
│ 5–15s         │ crowded  │ any   │ GLANCE_CARD        │
│ > 15s         │ low      │ any   │ FULL_VOICE         │
│ > 15s         │ crowded  │ any   │ BRIEF_TEXT_PROMPT  │
└───────────────┴──────────┴───────┴────────────────────┘

Note: noise does not affect mode — audio is delivered via earphones.
crowd accepts "low" or "crowded"; any other value is treated as "low".
"""

import logging
from dataclasses import dataclass

from rag_engine import RAGEngine

logger = logging.getLogger(__name__)

# Per-mode hard character caps (safety net — prompts already guide length)
# GLANCE_CARD: ~20 words ≈ 120 chars → cap at 160
# BRIEF_TEXT / BRIEF_TEXT_PROMPT: ~50–60 words ≈ 350 chars → cap at 450
# FULL_VOICE: ~100 words ≈ 700 chars → cap at 700
MODE_MAX_LENGTH: dict[str, int | None] = {
    "GLANCE_CARD":        160,
    "BRIEF_TEXT":         450,
    "BRIEF_TEXT_PROMPT":  450,
    "FULL_VOICE":         700,
    "NAVIGATION":         400,
    "SHOP":               600,
}

# Keep old names as aliases so nothing outside breaks if they were imported
BRIEF_MAX = 450
FULL_MAX  = 700

GAZE_THRESHOLD_INTEREST = 5.0   # seconds — below this, visitor is passing by
GAZE_THRESHOLD_ENGAGED  = 15.0  # seconds — above this, visitor is deeply engaged


@dataclass
class RouterDecision:
    mode:      str         # NO_RESPONSE | BRIEF_TEXT | GLANCE_CARD | FULL_VOICE | BRIEF_TEXT_PROMPT
    answer:    str         # text answer (empty for NO_RESPONSE)
    xr_action: str | None  # extra hint for the AR layer
    reason:    str         # human-readable explanation of why this mode was chosen


def _decide_mode(sensor_state: dict) -> tuple[str, str, str | None]:
    """
    Returns (mode, reason, xr_action) based on sensor state.
    Pure function — no side effects.
    """
    gaze_duration = float(sensor_state.get("gaze_duration", 0.0))
    crowd         = sensor_state.get("crowd", "low")   # "low" | "crowded"
    is_crowded    = crowd == "crowded"

    if gaze_duration < GAZE_THRESHOLD_INTEREST:
        return ("NO_RESPONSE", "gaze < 5s — visitor is passing by, do not interrupt", None)

    if gaze_duration < GAZE_THRESHOLD_ENGAGED:
        if is_crowded:
            return (
                "GLANCE_CARD",
                f"gaze={gaze_duration:.1f}s, crowded — show minimal info card",
                "show_card",
            )
        return (
            "BRIEF_TEXT",
            f"gaze={gaze_duration:.1f}s, low crowd — offer brief text with optional voice",
            None,
        )

    # gaze >= 15s
    if is_crowded:
        return (
            "BRIEF_TEXT_PROMPT",
            f"gaze={gaze_duration:.1f}s, crowded — show text and nudge toward a quieter spot",
            "show_quiet_prompt",
        )
    return (
        "FULL_VOICE",
        f"gaze={gaze_duration:.1f}s, low crowd — deliver full immersive experience",
        None,
    )


def route(question: str, rag: RAGEngine, state: dict, history: list[dict] | None = None) -> RouterDecision:
    """
    Main entry point.

    Args:
        question: visitor's natural-language question
        rag:      RAGEngine instance (pre-loaded, injected by server.py)
        state:    flat dict from Unity: {"gaze_duration": float, "crowd": str, "noise": str}

    Returns:
        RouterDecision with mode, answer, xr_action, and reason
    """
    mode, reason, xr_action = _decide_mode(state)
    logger.info("router_decision", extra={"mode": mode, "reason": reason})

    if mode == "NO_RESPONSE":
        return RouterDecision(mode=mode, answer="", xr_action=xr_action, reason=reason)

    max_len = MODE_MAX_LENGTH.get(mode)
    rag_result = rag.query(question, mode=mode, max_length=max_len, history=history)

    return RouterDecision(
        mode=mode,
        answer=rag_result["answer"],
        xr_action=xr_action,
        reason=reason,
    )
