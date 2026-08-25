"""Regression tests for the logging on the exhibit-recognition branch.

An unrecognised camera frame is the *common* case (bad angle, poor light,
something that isn't one of the twelve sculptures), so this branch has to be
the safest code in the pipeline. It wasn't: `extra={"name": ...}` collides
with a stdlib LogRecord attribute and made logging.makeRecord raise KeyError,
turning every unrecognised frame into a 500 for both /ask and
/v1/chat/completions.
"""

import logging

import numpy as np
import pytest

import qa_pipeline
from logging_config import configure_logging


@pytest.fixture
def json_logging():
    """The real JSON handler, so an unloggable `extra` fails here as in prod."""
    configure_logging()


@pytest.fixture
def stub_frame(monkeypatch):
    """Skip base64/JPEG decoding — the frame contents are irrelevant here."""
    monkeypatch.setattr(qa_pipeline, "_b64_to_frame", lambda _b64: np.zeros((2, 2, 3), np.uint8))


@pytest.mark.parametrize("recognition", [
    {"name": "unknown", "confidence": "high"},
    {"name": "Venus de Milo", "confidence": "low"},
    {},
])
def test_unrecognised_frame_answers_instead_of_raising(
    monkeypatch, stub_frame, json_logging, recognition
):
    monkeypatch.setattr(qa_pipeline, "recognize_exhibit", lambda *a, **k: recognition)

    result = qa_pipeline.run(
        question="What am I looking at?",
        image_b64="ignored",
        rag=None,  # never reached: an unmatched scan short-circuits before RAG
        mode="BRIEF_TEXT",
    )

    assert result["exhibit"] == ""
    assert "identify" in result["answer"]


def test_recognition_error_is_logged_without_raising(monkeypatch, stub_frame, json_logging):
    monkeypatch.setattr(qa_pipeline, "recognize_exhibit", lambda *a, **k: {"error": "boom"})

    result = qa_pipeline.run(
        question="What am I looking at?", image_b64="ignored", rag=None, mode="BRIEF_TEXT")

    assert result["exhibit"] == ""


def test_no_extra_key_shadows_a_logrecord_attribute():
    """The guard that would have caught this at review time, for every call site."""
    reserved = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
    record = logging.LogRecord("qa", logging.INFO, "", 0, "", (), None)
    for key in ("confidence", "recognized_name", "error", "mode"):
        assert key not in reserved, f"extra={{'{key}': ...}} would raise KeyError"
        assert not hasattr(record, key)
