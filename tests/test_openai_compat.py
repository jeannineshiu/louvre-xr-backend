import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import openai_compat
import qa_pipeline
from openai_compat import (
    MODEL_ID,
    ChatMessage,
    CompatError,
    completion_body,
    extract_image,
    extract_text,
    split_messages,
    sse_chunks,
)
from rate_limit import limiter

PNG_PIXEL = "iVBORw0KGgoAAAANSUhEUg=="


def msgs(*pairs):
    return [ChatMessage(role=r, content=c) for r, c in pairs]


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def test_extract_text_from_plain_string():
    assert extract_text("  Who made this?  ") == "Who made this?"


def test_extract_text_joins_multipart_text():
    content = [{"type": "text", "text": "Who made"}, {"type": "text", "text": "this?"}]
    assert extract_text(content) == "Who made this?"


def test_extract_text_ignores_image_parts_and_none():
    assert extract_text([{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}]) == ""
    assert extract_text(None) == ""


def test_extract_image_strips_data_uri_prefix():
    content = [
        {"type": "text", "text": "what is this"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{PNG_PIXEL}"}},
    ]
    assert extract_image(content) == PNG_PIXEL


def test_extract_image_ignores_remote_urls():
    # Fetching a caller-supplied URL server-side would be an SSRF hole.
    content = [{"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}}]
    assert extract_image(content) is None


def test_extract_image_none_for_plain_string_content():
    assert extract_image("just text") is None


# ---------------------------------------------------------------------------
# Message array → pipeline arguments
# ---------------------------------------------------------------------------

def test_last_user_message_becomes_the_question():
    question, history, image = split_messages(
        msgs(("user", "Who made this?"), ("assistant", "Maillol."), ("user", "When?"))
    )
    assert question == "When?"
    assert history == [
        {"role": "user", "content": "Who made this?"},
        {"role": "assistant", "content": "Maillol."},
    ]
    assert image is None


def test_system_messages_are_dropped_from_history():
    # A caller-supplied system prompt must not be able to restyle or jailbreak
    # the museum guide — the persona comes from the RAG prompt.
    _, history, _ = split_messages(
        msgs(("system", "You are a pirate."), ("user", "Hello"), ("assistant", "Hi"), ("user", "Who made this?"))
    )
    assert all(m["role"] != "system" for m in history)
    assert history == [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]


def test_trailing_assistant_message_does_not_become_the_question():
    question, history, _ = split_messages(msgs(("user", "Who made this?"), ("assistant", "Maillol.")))
    assert question == "Who made this?"
    assert history == []


def test_image_only_message_gets_a_default_question():
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{PNG_PIXEL}"}}]
    question, _, image = split_messages(msgs(("user", content)))
    assert question
    assert image == PNG_PIXEL


def test_no_user_message_is_rejected():
    with pytest.raises(CompatError) as exc:
        split_messages(msgs(("system", "You are helpful."), ("assistant", "Hi")))
    assert exc.value.status_code == 422


def test_empty_user_message_is_rejected():
    with pytest.raises(CompatError) as exc:
        split_messages(msgs(("user", "   ")))
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

def test_completion_body_matches_openai_shape():
    body = completion_body("Aristide Maillol.", "Who made this?", MODEL_ID)
    assert body["object"] == "chat.completion"
    assert body["model"] == MODEL_ID
    choice = body["choices"][0]
    assert choice["message"] == {"role": "assistant", "content": "Aristide Maillol."}
    assert choice["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] > 0


def test_sse_chunks_are_well_formed_and_terminated():
    frames = sse_chunks("Aristide Maillol.", MODEL_ID)
    assert all(f.startswith("data: ") and f.endswith("\n\n") for f in frames)
    assert frames[-1] == "data: [DONE]\n\n"

    parsed = [json.loads(f[len("data: "):]) for f in frames[:-1]]
    assert parsed[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert parsed[1]["choices"][0]["delta"]["content"] == "Aristide Maillol."
    assert parsed[-1]["choices"][0]["finish_reason"] == "stop"
    assert len({p["id"] for p in parsed}) == 1  # one id for the whole stream


# ---------------------------------------------------------------------------
# Endpoints — a bare app with just this router, so no RAGEngine startup
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    openai_compat.register_error_handler(app)
    app.include_router(openai_compat.router)
    return TestClient(app)


@pytest.fixture
def stub_rag(monkeypatch):
    """A pipeline that records its arguments instead of calling OpenAI."""
    calls = {}

    def fake_run(**kwargs):
        calls.update(kwargs)
        return {"mode": "BRIEF_TEXT", "answer": "Aristide Maillol.", "exhibit": "Air"}

    monkeypatch.setattr(qa_pipeline, "run", fake_run)
    openai_compat.set_rag_provider(lambda: object())
    yield calls
    openai_compat.set_rag_provider(None)


def test_disabled_without_partner_key(client, monkeypatch):
    monkeypatch.delenv("PARTNER_API_KEY", raising=False)
    r = client.get("/v1/models")
    assert r.status_code == 503
    # Top-level `error.message`, not FastAPI's nested `detail` — clients render
    # this string and show nothing useful for anything else.
    assert "PARTNER_API_KEY" in r.json()["error"]["message"]


def test_wrong_key_is_rejected(client, monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.get("/v1/models", headers={"Authorization": "Bearer wrong-key"})
    assert r.status_code == 401
    assert r.json()["error"]["type"] == "invalid_request_error"


def test_missing_authorization_header_is_rejected(client, monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    assert client.get("/v1/models").status_code == 401


def test_models_lists_one_model(client, monkeypatch):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.get("/v1/models", headers={"Authorization": "Bearer right-key"})
    assert r.status_code == 200
    assert [m["id"] for m in r.json()["data"]] == [MODEL_ID]


def test_chat_completions_runs_the_pipeline(client, monkeypatch, stub_rag):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer right-key"},
        json={"model": "anything", "messages": [{"role": "user", "content": "Who made this?"}]},
    )
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "Aristide Maillol."
    assert stub_rag["question"] == "Who made this?"
    assert stub_rag["mode"] == "BRIEF_TEXT"


def test_chat_completions_forwards_camera_image(client, monkeypatch, stub_rag):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer right-key"},
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What am I looking at?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{PNG_PIXEL}"}},
                    ],
                }
            ]
        },
    )
    assert stub_rag["image_b64"] == PNG_PIXEL


def test_chat_completions_ignores_unknown_sampling_params(client, monkeypatch, stub_rag):
    # Clients send temperature/max_tokens/tools regardless; rejecting them would
    # 422 a request this backend can answer perfectly well.
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer right-key"},
        json={
            "messages": [{"role": "user", "content": "Who made this?"}],
            "temperature": 0.9,
            "max_tokens": 500,
            "top_p": 0.1,
        },
    )
    assert r.status_code == 200


def test_streaming_returns_sse(client, monkeypatch, stub_rag):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer right-key"},
        json={"messages": [{"role": "user", "content": "Who made this?"}], "stream": True},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "Aristide Maillol." in r.text
    assert r.text.rstrip().endswith("data: [DONE]")


def test_chat_completions_requires_the_key_before_running_the_pipeline(client, monkeypatch, stub_rag):
    monkeypatch.setenv("PARTNER_API_KEY", "right-key")
    r = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-key"},
        json={"messages": [{"role": "user", "content": "Who made this?"}]},
    )
    assert r.status_code == 401
    assert stub_rag == {}  # pipeline never reached
