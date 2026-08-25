"""Shared Whisper speech-to-text.

Two surfaces transcribe audio: `/transcribe` (demo.html's mic, the VR client)
and `/v1/audio/transcriptions` (OpenAI-compatible clients). They differ only in
how they dress up the result — the Whisper call, the domain prompt, and the
language sanity check are identical, so they live here rather than being copied
into the second surface and drifting from the first.

This module deliberately raises on failure. Degrading to empty text is right for
`/transcribe`, whose callers would rather show nothing than an error; it is
wrong for the compat layer, where a client that receives `{"text": ""}` has no
way to tell "you said nothing" from "the backend is broken". Each caller picks.
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "whisper-1"

# Whisper's own hard limit on upload size. Checked before the call so an
# oversized clip fails fast and locally, with a message that says what happened,
# instead of spending a round trip to be rejected by the API.
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Fed to Whisper as a transcription prompt: proper nouns from the knowledge
# base plus a short phrase per officially-supported language (see README's
# "Officially supported languages" note). Whisper has no reliable language
# auto-detection on short, noisy, or accented clips — a few seconds of "tell
# me about X" is exactly the case where it can lock onto the wrong language
# entirely (observed in production: German audio transcribed as Danish
# gibberish). A domain prompt biases both vocabulary and the implicit
# language signal toward what a visitor here actually says, without forcing
# a single `language` param that would break the other three languages.
PROMPT = (
    "Louvre museum sculpture guide. Sophie. Winged Victory of Samothrace, Venus de Milo, "
    "Cupid and Psyche, Borghese Gladiator, Dying Slave, Seated Scribe, Bastet Cat Statue, "
    "La Siesta, Air, La Nuit, L'Hommage à Cézanne, Miles Franklin. "
    "Tell me about... Erzähl mir etwas über... Parlez-moi de... 告訴我關於..."
)

# Whisper's verbose_json `language` field is the full English name, lowercase
# (e.g. "german"), not an ISO code — matches what's actually been observed.
SUPPORTED_LANGS = {"english", "french", "german", "chinese"}

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """The process-wide OpenAI client, created on first use."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def transcribe(filename: str, content: bytes, language: str | None = None) -> str:
    """Transcribe one audio clip. Returns the stripped transcript.

    Args:
        filename: original name — Whisper infers the container format from its
                  extension, so a wrong or missing one is worth preserving
                  rather than normalising away.
        content:  raw audio bytes.
        language: ISO-639-1 hint. Omit to let PROMPT steer detection, which is
                  what every first-party caller does; the compat layer passes
                  one through only when the client explicitly set it.

    Raises:
        ValueError:  empty or oversized audio.
        Exception:   whatever the OpenAI SDK raises.
    """
    if not content:
        raise ValueError("audio file is empty")
    if len(content) > MAX_AUDIO_BYTES:
        raise ValueError(
            f"audio file is {len(content) // 1024 // 1024} MB; the limit is "
            f"{MAX_AUDIO_BYTES // 1024 // 1024} MB"
        )

    extra = {"language": language} if language else {}
    result = get_client().audio.transcriptions.create(
        model=MODEL,
        file=(filename or "audio.webm", content),
        prompt=PROMPT,
        response_format="verbose_json",
        **extra,
    )

    detected_lang = (getattr(result, "language", "") or "").lower()
    if detected_lang and detected_lang not in SUPPORTED_LANGS:
        # Not necessarily wrong — Whisper's language field is a best-effort
        # guess too — but it's the strongest signal we have that this
        # transcript may be garbled, since every visitor-facing feature
        # only supports these four languages. Logged (and, if SENTRY_DSN
        # is set, reported) purely for visibility into how often this
        # happens in practice; the transcript is still returned as-is.
        logger.warning("transcribe_unexpected_language", extra={"detected_lang": detected_lang})

    return (result.text or "").strip()
