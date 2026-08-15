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
import logging
import re

import cv2
import numpy as np

from context_router import MODE_MAX_LENGTH, route
from exhibit_recognizer import recognize_exhibit
from navigation_routes import EXHIBIT_NAMES, ROUTES
from rag_engine import RAGEngine

logger = logging.getLogger(__name__)


def _b64_to_frame(image_b64: str) -> np.ndarray | None:
    """Decode a base64 image string to a BGR numpy array. Returns None on failure."""
    try:
        img_bytes = base64.b64decode(image_b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — any decode failure should silently return None
        return None


DEFAULT_MODE = "FULL_VOICE"


# ---------------------------------------------------------------------------
# NAVIGATION mode — deterministic dict lookup, no LLM.
#
# The RAG index has no room/wing/floor data (see rag_engine.py), so routing
# NAVIGATION questions through the LLM produced fluent, plausible, and WRONG
# room numbers. Real directions live in navigation_routes.ROUTES; this just
# resolves which two exhibits the visitor means and looks the route up.
# ---------------------------------------------------------------------------

_NAME_TO_ID = {name.lower(): eid for eid, name in EXHIBIT_NAMES.items()}

_NAVIGATION_HELP = (
    "I can give walking directions between these galleries: "
    + ", ".join(EXHIBIT_NAMES.values())
    + ". Let me know which one you're standing at and which one you'd like to reach."
)


def _matched_exhibit_ids(text: str) -> list[tuple[str, str]]:
    """(name, id) pairs whose name appears in text, longest name first."""
    text_low = text.lower()
    hits = {eid: name for name, eid in _NAME_TO_ID.items() if name in text_low}
    return sorted(hits.items(), key=lambda pair: len(pair[1]), reverse=True)


def _navigation_answer(question: str, known_from_name: str | None) -> str:
    """Resolve (from, to) exhibit ids from the question + known position, and
    return the deterministic directions from navigation_routes.ROUTES. Declines
    with a clarifying message rather than guessing when either end is ambiguous."""
    candidates = _matched_exhibit_ids(question)
    matched_ids = [eid for eid, _ in candidates]

    from_id = _NAME_TO_ID.get((known_from_name or "").lower())
    to_id = None

    if from_id:
        others = [eid for eid in matched_ids if eid != from_id]
        to_id = others[0] if others else None
    else:
        text_low = question.lower()
        from_match = re.search(r"from\s+(.+?)(?:\s+to\s+|$)", text_low)
        to_match = re.search(r"\bto\s+(.+?)(?:\s+from\s+|$)", text_low)
        for eid, name in candidates:
            if from_match and name in from_match.group(1):
                from_id = from_id or eid
            if to_match and name in to_match.group(1):
                to_id = to_id or eid

    if not from_id or not to_id:
        return _NAVIGATION_HELP

    if from_id == to_id:
        return f"You are already at {EXHIBIT_NAMES[from_id]}."

    directions = ROUTES.get((from_id, to_id))
    return directions if directions else _NAVIGATION_HELP


# ---------------------------------------------------------------------------
# Chit-chat short-circuit — greetings/thanks/small-talk skip retrieval and
# the GPT-4o call entirely. Only fires when the ENTIRE (stripped) question
# matches, so a real question that happens to start with "hi" (e.g. "hi,
# what is this statue made of?") still goes through RAG normally.
# ---------------------------------------------------------------------------

_PUNCT_TAIL = r"[\s!?~。！，,.]*$"

# Checked in order; first match wins. Each category gets its own reply since
# "hi" and "thanks" don't take the same response.
_CHITCHAT_CATEGORIES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?:hi|hello|hey|hiya|yo|howdy|good\s?(?:morning|afternoon|evening|day)|"
                r"bonjour|salut|hallo|guten\s?(?:tag|morgen|abend)|servus|moin|"
                r"你好|哈囉|嗨)" + _PUNCT_TAIL, re.IGNORECASE), "greeting"),
    (re.compile(r"^(?:thanks?(?:\s?you)?(?:\s?(?:very|so)\s?much)?|ty|cheers|"
                r"merci(?:\s?beaucoup)?|danke(?:\s?sch[oö]n)?|vielen\s?dank|"
                r"謝謝|謝謝你|感謝)" + _PUNCT_TAIL, re.IGNORECASE), "thanks"),
    (re.compile(r"^(?:bye|goodbye|see\s?you(?:\s?later)?|au\s?revoir|"
                r"auf\s?wiedersehen|tsch[uü]ss|tschau|"
                r"再見|掰掰)" + _PUNCT_TAIL, re.IGNORECASE), "bye"),
    (re.compile(r"^(?:ok(?:ay)?|cool|great|nice|awesome|got\s?it|sounds\s?good|lol|haha|"
                r"super|klasse|gut)" + _PUNCT_TAIL, re.IGNORECASE), "ack"),
]

_CHINESE_CHAR_PATTERN = re.compile(r"[一-鿿]")
_FRENCH_WORD_PATTERN = re.compile(r"\b(?:bonjour|salut|merci|au\s?revoir)\b", re.IGNORECASE)
_GERMAN_WORD_PATTERN = re.compile(
    r"\b(?:hallo|guten\s?(?:tag|morgen|abend)|servus|moin|danke(?:\s?sch[oö]n)?|"
    r"vielen\s?dank|auf\s?wiedersehen|tsch[uü]ss|tschau)\b", re.IGNORECASE)

_CHITCHAT_REPLIES: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Hello! I'm Sophie — ask me about any of the sculptures here.",
        "fr": "Bonjour ! Je suis Sophie, n'hésitez pas à me poser des questions sur les sculptures ici.",
        "de": "Hallo! Ich bin Sophie — fragen Sie mich gerne alles zu den Skulpturen hier.",
        "zh": "你好！我是蘇菲，歡迎問我這裡的雕塑作品。",
    },
    "thanks": {
        "en": "You're welcome! Let me know if you'd like to hear about any of the sculptures here.",
        "fr": "Avec plaisir ! N'hésitez pas à me demander si vous voulez en savoir plus sur les sculptures.",
        "de": "Gern geschehen! Fragen Sie mich einfach, wenn Sie mehr über die Skulpturen hier erfahren möchten.",
        "zh": "不客氣！如果想了解這裡的雕塑作品，隨時可以問我。",
    },
    "bye": {
        "en": "Goodbye! Enjoy the rest of your visit.",
        "fr": "Au revoir ! Profitez bien de votre visite.",
        "de": "Auf Wiedersehen! Genießen Sie den Rest Ihres Besuchs.",
        "zh": "再見！祝你參觀愉快。",
    },
    "ack": {
        "en": "Great! Let me know if you have any other questions.",
        "fr": "Parfait ! N'hésitez pas si vous avez d'autres questions.",
        "de": "Sehr gut! Melden Sie sich, falls Sie noch weitere Fragen haben.",
        "zh": "太好了！如果還有其他問題歡迎再問我。",
    },
}


def _chitchat_reply(question: str) -> str | None:
    """A canned reply if `question` is pure small-talk, else None. Crude
    language pick (Chinese char / French / German keyword presence) — good
    enough for a one-line pleasantry; anything more contentful falls through
    to RAG, which already handles language matching properly (see rag_engine
    _PERSONA_GUIDE). Supported languages: en, fr, de, zh — keep this list in
    sync with _PERSONA_GUIDE and demo.html's NAV_KEYWORDS/SHOP_KEYWORDS."""
    stripped = question.strip()
    if not stripped:
        return None

    category = next((name for pattern, name in _CHITCHAT_CATEGORIES if pattern.match(stripped)), None)
    if category is None:
        return None

    if _CHINESE_CHAR_PATTERN.search(stripped):
        lang = "zh"
    elif _FRENCH_WORD_PATTERN.search(stripped):
        lang = "fr"
    elif _GERMAN_WORD_PATTERN.search(stripped):
        lang = "de"
    else:
        lang = "en"
    return _CHITCHAT_REPLIES[category][lang]


def run(
    question:      str,
    image_b64:     str | None,
    rag:           RAGEngine,
    api_state:     dict | None  = None,
    mode:          str | None   = None,
    history:       list[dict] | None = None,
    known_exhibit: str | None   = None,
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
        known_exhibit: Exhibit name the frontend already knows the visitor is facing
                   (e.g. a preset WebXR splat). Used to anchor the answer when no
                   image is sent or recognition fails. Image recognition takes priority.

    Returns:
        {
            "mode":    str,
            "answer":  str,
            "exhibit": str,
        }
    """
    # Step 1: Identify the exhibit.
    # If the frontend already knows which sculpture the visitor is facing
    # (e.g. a preset WebXR splat → exhibit), use it directly and skip the
    # GPT-4o Vision call. Otherwise fall back to recognising it from the frame.
    exhibit_name = ""
    image_scanned = False  # True when an image was provided (regardless of recognition result)
    if known_exhibit:
        exhibit_name = known_exhibit
    elif image_b64:
        frame = _b64_to_frame(image_b64)
        if frame is not None:
            image_scanned = True
            recognition = recognize_exhibit(frame, detail="high")
            if "error" in recognition:
                logger.warning("exhibit_recognition_error", extra={"error": recognition["error"]})
            elif (
                recognition.get("confidence") == "high"
                and recognition.get("name", "unknown").lower() != "unknown"
            ):
                exhibit_name = recognition["name"]
            else:
                logger.info("exhibit_recognition_no_match", extra={
                    "confidence": recognition.get("confidence"),
                    "name":       recognition.get("name"),
                })

    # If an image was scanned but not matched to any of the recognised sculptures
    # (and the frontend didn't tell us which exhibit it is), return a clear
    # explanation instead of letting the RAG guess.
    if image_scanned and not exhibit_name:
        return {
            "mode":    mode or DEFAULT_MODE,
            "answer": (
                "I wasn't able to identify this sculpture as one of the works in my system. "
                "I can tell you about: the Winged Victory of Samothrace, Venus de Milo, "
                "Cupid and Psyche, the Borghese Gladiator, the Dying Slave, the Seated Scribe, "
                "the Bastet Cat Statue, Air, La Nuit, L'Hommage à Cézanne, La Siesta, "
                "or the Miles Franklin Statue in Hurstville, Sydney. "
                "Try scanning again with the sculpture clearly in frame, "
                "or ask me about any of those works."
            ),
            "exhibit": "",
        }

    # Step 2: Enrich question with exhibit context if recognised
    enriched_question = (
        f"[Regarding: {exhibit_name}] {question}" if exhibit_name else question
    )

    # Step 2.5: Pure small-talk ("hi", "thanks", ...) skips retrieval + the
    # GPT-4o call entirely — see _chitchat_reply. Checked after exhibit
    # recognition (so a scanned image is still reflected in the response)
    # but before every mode branch below, since none of them need an LLM
    # call to answer a greeting.
    if mode != "NAVIGATION":
        chitchat_answer = _chitchat_reply(question)
        if chitchat_answer is not None:
            logger.info("chitchat_short_circuit", extra={"mode": mode or DEFAULT_MODE})
            return {
                "mode":    mode or DEFAULT_MODE,
                "answer":  chitchat_answer,
                "exhibit": exhibit_name,
            }

    # Step 3: Decide mode and generate answer
    if mode == "NAVIGATION":
        # Deterministic route lookup — never goes through the RAG/LLM path.
        return {
            "mode":    mode,
            "answer":  _navigation_answer(question, exhibit_name),
            "exhibit": exhibit_name,
        }

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
