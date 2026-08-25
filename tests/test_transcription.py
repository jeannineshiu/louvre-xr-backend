"""Guards in the shared Whisper helper (transcription.py).

Both surfaces reach OpenAI through this module, so the cheap local checks —
empty clip, oversized clip — are tested once here rather than per endpoint.
"""

import pytest

import transcription


def test_empty_audio_raises_before_calling_openai(monkeypatch):
    monkeypatch.setattr(transcription, "get_client", lambda: pytest.fail("called OpenAI"))
    with pytest.raises(ValueError, match="empty"):
        transcription.transcribe("speech.webm", b"")


def test_oversized_audio_raises_before_calling_openai(monkeypatch):
    # Whisper rejects these anyway; failing locally saves the upload and says why.
    monkeypatch.setattr(transcription, "get_client", lambda: pytest.fail("called OpenAI"))
    with pytest.raises(ValueError, match="limit"):
        transcription.transcribe("speech.webm", b"\x00" * (transcription.MAX_AUDIO_BYTES + 1))


def test_language_is_omitted_rather_than_sent_empty(monkeypatch):
    """An empty `language` would be a hint meaning nothing; the key must be absent."""
    sent = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            sent.update(kwargs)
            return type("R", (), {"text": " hello ", "language": "english"})()

    monkeypatch.setattr(transcription, "get_client",
                        lambda: type("C", (), {"audio": type("A", (), {"transcriptions": FakeTranscriptions()})()})())

    assert transcription.transcribe("speech.webm", b"audio") == "hello"
    assert "language" not in sent
    assert sent["prompt"] == transcription.PROMPT
