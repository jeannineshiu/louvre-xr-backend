"""
MuseXR — OpenAI TTS
Generates Sophie's voice using OpenAI's speech API and saves as a temporary mp3 file.
Uses the existing OPENAI_API_KEY — no additional service required.
"""

import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from cache import TTLCache

load_dotenv()

logger = logging.getLogger(__name__)

# Sophie's voice — options: alloy, echo, fable, onyx, nova, shimmer
SOPHIE_VOICE = os.environ.get("SOPHIE_VOICE", "nova")

AUDIO_DIR = Path("temp_audio")
AUDIO_DIR.mkdir(exist_ok=True)

_client: OpenAI | None = None

# (text, voice) → file_id. Greetings and common answers ("Who made this?")
# repeat across visitors/rooms; without this every repeat re-billed OpenAI
# TTS and wrote a fresh duplicate mp3 to disk. temp_audio/ isn't cleaned up
# elsewhere (Railway wipes it on redeploy), so a cached file_id stays valid
# for the life of the process — TTL here just bounds cache memory, not
# correctness.
_audio_cache = TTLCache(ttl_seconds=3600, maxsize=256)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def generate_sophie_audio(text: str) -> str | None:
    """
    Generate TTS via OpenAI and save the mp3 to temp_audio/, reusing a cached
    file for identical (text, voice) pairs. Returns the file_id (UUID string)
    on success, None on failure.
    """
    key = (text, SOPHIE_VOICE)
    cached = _audio_cache.get(key)
    if cached is not TTLCache.MISSING:
        return cached

    file_id = _synthesize(text)
    if file_id is not None:
        # Don't cache a failure — a transient API/network error shouldn't
        # keep returning None for every repeat of the same text for the
        # rest of the TTL window.
        _audio_cache.set(key, file_id)
    return file_id


def _synthesize(text: str) -> str | None:
    try:
        response = _get_client().audio.speech.create(
            model="tts-1",
            voice=SOPHIE_VOICE,
            input=text,
        )
        file_id   = str(uuid.uuid4())
        file_path = AUDIO_DIR / f"{file_id}.mp3"
        response.stream_to_file(str(file_path))
        return file_id

    except Exception:
        # Degrades to "no audio" for the caller (see generate_sophie_audio) —
        # logged (and, if SENTRY_DSN is set in server.py, reported) so a
        # persistent TTS outage is visible instead of silently invisible.
        logger.exception("tts_synthesis_failed")
        return None
