"""
MuseXR — OpenAI TTS
Generates Sophie's voice using OpenAI's speech API and saves as a temporary mp3 file.
Uses the existing OPENAI_API_KEY — no additional service required.
"""

import os
import uuid
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Sophie's voice — options: alloy, echo, fable, onyx, nova, shimmer
SOPHIE_VOICE = os.environ.get("SOPHIE_VOICE", "nova")

AUDIO_DIR = Path("temp_audio")
AUDIO_DIR.mkdir(exist_ok=True)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def generate_sophie_audio(text: str) -> str | None:
    """
    Generate TTS via OpenAI and save the mp3 to temp_audio/.
    Returns the file_id (UUID string) on success, None on failure.
    """
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
        return None
