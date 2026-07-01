"""
MuseXR — ElevenLabs TTS
Generates Sophie's voice from text and saves as a temporary mp3 file.
"""

import os
import uuid
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
SOPHIE_VOICE_ID    = os.environ.get("SOPHIE_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")

AUDIO_DIR = Path("temp_audio")
AUDIO_DIR.mkdir(exist_ok=True)


def generate_sophie_audio(text: str) -> str | None:
    """
    Send text to ElevenLabs TTS and save the mp3 to temp_audio/.
    Returns the file_id (UUID string) on success, None on failure.

    The caller constructs the public URL:
        https://<host>/audio/<file_id>
    """
    if not ELEVENLABS_API_KEY:
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{SOPHIE_VOICE_ID}"
    headers = {
        "xi-api-key":   ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability":        0.50,
            "similarity_boost": 0.75,
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None

        file_id   = str(uuid.uuid4())
        file_path = AUDIO_DIR / f"{file_id}.mp3"
        file_path.write_bytes(resp.content)
        return file_id

    except Exception:
        return None
