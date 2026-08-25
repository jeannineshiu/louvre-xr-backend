"""OpenAI-compatible chat layer.

Third-party glasses clients (RokidAIAssistant and anything else that offers a
"custom endpoint" box) speak one protocol: a base URL onto which they append
`chat/completions`, a `{model, messages}` body, and often a `GET /v1/models`
call to populate a model picker. `/ask` speaks none of that — it has its own
schema, and the model is chosen server-side — so pointing such a client at
`.../ask` makes it request `.../ask/chat/completions` and get a 404, with the
model name field a red herring.

This module is a thin translation layer over the same `qa_pipeline.run` that
`/ask` uses, so there is one answer path and no second copy of the QA logic to
drift. It deliberately does NOT expose the museum-specific surface (`mode`,
`state` routing, `voice`/`audio_url`, `splat`): a generic chat client has
nowhere to put those. Camera frames are the exception — clients send them as
OpenAI vision content parts, which map cleanly onto the pipeline's `image_b64`,
so exhibit recognition still works here. Speech is the other exception, for
the same reason: a client that offers a "custom endpoint" for chat usually
offers one for speech recognition too, and expects it to be OpenAI's
`POST /v1/audio/transcriptions`.

Access: gated on PARTNER_API_KEY. Unset means these routes are switched off
entirely (503) rather than open — an unauthenticated /v1/chat/completions on a
public host is actively scanned for, and every call spends real money on the
one shared OpenAI key.
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

import qa_pipeline
import transcription
from rate_limit import PARTNER_RATE_LIMIT, configured_partner_key, is_partner, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])

# The single model id this backend advertises. Clients that let you type a free
# -form model name can send anything — the value is ignored, since the actual
# models are fixed server-side (gpt-4o for chat and Vision, see rag_engine.py
# and exhibit_recognizer.py). Advertising one stable id is what makes a model
# picker work at all.
MODEL_ID = "louvre-sophie"

# Generic chat clients render text and nothing else — no glance card, no audio
# player — so the pipeline's mode routing has no meaning here. BRIEF_TEXT is the
# text-shaped mode; picking it explicitly also avoids NO_RESPONSE, which the
# context router can return and which would look like a broken bot.
_COMPAT_MODE = "BRIEF_TEXT"

# Injected by server.py at import time so this module doesn't import server
# (which imports this one). Returns the RAGEngine singleton, or None before
# startup has finished loading it.
_rag_provider = None


def set_rag_provider(provider) -> None:
    """Register the callable that returns the RAGEngine singleton."""
    global _rag_provider
    _rag_provider = provider


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    # `content` is a plain string in most clients but a list of typed parts
    # when an image is attached; both are accepted. Null content appears on
    # assistant tool-call messages, which this backend has no tools for.
    model_config = ConfigDict(extra="ignore")

    role:    str
    content: str | list[dict] | None = None


class ChatCompletionRequest(BaseModel):
    # extra="ignore" so the sampling knobs every client sends (temperature,
    # max_tokens, top_p, presence_penalty, tools, ...) are accepted and dropped
    # rather than 422-ing a request this backend could otherwise answer. They
    # have no effect: generation parameters are fixed in rag_engine.py.
    model_config = ConfigDict(extra="ignore")

    messages: list[ChatMessage]
    model:    str | None = None
    stream:   bool = False


# ---------------------------------------------------------------------------
# Translation — pure functions, no I/O, so they're directly unit-testable
# ---------------------------------------------------------------------------

def extract_text(content: str | list[dict] | None) -> str:
    """Flatten message content to plain text.

    Multi-part content joins every text part with a space; non-text parts
    (images) are handled separately by extract_image.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    parts = [
        str(part.get("text", "")).strip()
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    ]
    return " ".join(p for p in parts if p).strip()


def extract_image(content: str | list[dict] | None) -> str | None:
    """Pull the first image out of multi-part content as bare base64.

    Clients send `{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`.
    The pipeline wants the base64 payload without the data-URI prefix. Remote
    http(s) image URLs are ignored rather than fetched: fetching an arbitrary
    caller-supplied URL server-side is an SSRF foot-gun, and no glasses client
    sends one — the camera frame is always inline.
    """
    if not isinstance(content, list):
        return None
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            continue
        url = part.get("image_url")
        url = url.get("url", "") if isinstance(url, dict) else str(url or "")
        if not url.startswith("data:"):
            continue
        _, _, payload = url.partition(",")
        if payload:
            return payload
    return None


def split_messages(messages: list[ChatMessage]) -> tuple[str, list[dict], str | None]:
    """Map an OpenAI message array onto the pipeline's (question, history, image).

    The last user message is the question; everything before it becomes history
    in the same {role, content} shape /ask already accepts. System messages are
    dropped — Sophie's persona and grounding rules come from the RAG prompt, and
    honouring a caller-supplied system prompt would let any client with the
    token restyle or jailbreak the museum guide.
    """
    last_user = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].role == "user":
            last_user = i
            break
    if last_user is None:
        raise CompatError(
            422,
            "messages must contain at least one message with role 'user'",
            "invalid_request_error",
        )

    question = extract_text(messages[last_user].content)
    image_b64 = extract_image(messages[last_user].content)
    if not question and image_b64:
        # An image with no text is a "what am I looking at?" gesture.
        question = "What am I looking at?"
    if not question:
        raise CompatError(422, "the last user message has no text content", "invalid_request_error")

    history = [
        {"role": m.role, "content": extract_text(m.content)}
        for m in messages[:last_user]
        if m.role in ("user", "assistant") and extract_text(m.content)
    ]
    return question, history, image_b64


def _estimate_tokens(text: str) -> int:
    """Rough token count for the usage block — ~4 characters per token.

    Clients display this; none of them bill on it. Running a real tokenizer for
    a cosmetic field isn't worth the dependency.
    """
    return max(1, len(text) // 4)


def completion_body(answer: str, question: str, model: str) -> dict:
    """A non-streaming chat.completion response object."""
    prompt_tokens = _estimate_tokens(question)
    completion_tokens = _estimate_tokens(answer)
    return {
        "id":      f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object":  "chat.completion",
        "created": int(time.time()),
        "model":   model,
        "choices": [
            {
                "index":         0,
                "message":       {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens":     prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens":      prompt_tokens + completion_tokens,
        },
    }


def sse_chunks(answer: str, model: str) -> list[str]:
    """The SSE frames for a streamed response, in order.

    The pipeline returns a finished string — retrieval and generation complete
    before anything can be sent — so this is a real stream in protocol only: one
    role frame, one content frame, one finish frame, then [DONE]. That is
    deliberate. A client that sets stream=true and receives a plain JSON body
    instead sits waiting for frames that never arrive and fails as an
    unexplained timeout, which is far harder to diagnose than a fast stream.
    """
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    def frame(delta: dict, finish_reason: str | None) -> str:
        payload = {
            "id":      chunk_id,
            "object":  "chat.completion.chunk",
            "created": created,
            "model":   model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return [
        frame({"role": "assistant"}, None),
        frame({"content": answer}, None),
        frame({}, "stop"),
        "data: [DONE]\n\n",
    ]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class CompatError(Exception):
    """An error to render in OpenAI's error shape.

    FastAPI's HTTPException would nest the body under `detail`, but clients read
    a top-level `error.message` and show nothing useful for anything else —
    which is how a plain misconfiguration ends up displayed as "unknown provider
    error". register_error_handler() below emits the shape they expect.
    """

    def __init__(self, status_code: int, message: str, err_type: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.err_type = err_type

    def body(self) -> dict:
        return {"error": {"message": self.message, "type": self.err_type, "code": None}}


def register_error_handler(app: FastAPI) -> None:
    """Wire CompatError into the app. Called by server.py."""

    @app.exception_handler(CompatError)
    async def _handle(request: Request, exc: CompatError):  # noqa: ARG001 - signature fixed by FastAPI
        return JSONResponse(status_code=exc.status_code, content=exc.body())


def require_partner(request: Request) -> None:
    """Fail closed unless the request carries the configured partner token."""
    if configured_partner_key() is None:
        raise CompatError(
            503,
            "The OpenAI-compatible API is not enabled on this server. "
            "Set PARTNER_API_KEY to enable it.",
            "service_unavailable",
        )
    if not is_partner(request):
        raise CompatError(
            401,
            "Invalid API key. Put the key issued for this backend in the client's API key field.",
            "invalid_request_error",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/models")
def list_models(request: Request):
    """Model list for clients that populate a picker before their first call."""
    require_partner(request)
    return {
        "object": "list",
        "data": [
            {
                "id":       MODEL_ID,
                "object":   "model",
                "created":  0,
                "owned_by": "louvre-xr-backend",
            }
        ],
    }


def _answer(body: ChatCompletionRequest) -> tuple[str, str, str]:
    """Run the QA pipeline for a chat request. Returns (answer, question, exhibit)."""
    rag = _rag_provider() if _rag_provider else None
    if rag is None:
        raise CompatError(503, "RAG engine not ready yet", "service_unavailable")

    question, history, image_b64 = split_messages(body.messages)

    start = time.monotonic()
    logger.info("openai_compat_received", extra={
        "question_len": len(question),
        "has_image":    bool(image_b64),
        "turns":        len(history),
        "stream":       body.stream,
    })

    try:
        result = qa_pipeline.run(
            question=question,
            image_b64=image_b64,
            api_state=None,
            mode=_COMPAT_MODE,
            rag=rag,
            history=history or None,
            known_exhibit=None,
        )
    except Exception:
        logger.exception("openai_compat_pipeline_failed")
        raise

    logger.info("openai_compat_completed", extra={
        "exhibit":     result["exhibit"],
        "answer_len":  len(result["answer"]),
        "duration_ms": round((time.monotonic() - start) * 1000),
    })
    return result["answer"], question, result["exhibit"]


@router.post("/chat/completions")
@limiter.limit(PARTNER_RATE_LIMIT)
async def chat_completions(body: ChatCompletionRequest, request: Request):
    """OpenAI-compatible chat endpoint, streaming or not."""
    require_partner(request)

    # qa_pipeline.run is blocking (embeddings, Vision, chat completion); keep it
    # off the event loop the same way FastAPI does for /ask's sync handler.
    answer, question, _ = await run_in_threadpool(_answer, body)
    model = body.model or MODEL_ID

    if body.stream:
        def gen():
            yield from sse_chunks(answer, model)
        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            # Railway sits behind a proxy that will otherwise buffer the whole
            # response and defeat the point of streaming.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return completion_body(answer, question, model)


# The transcription models OpenAI advertises. The value is ignored — this
# backend transcribes with whisper-1 (see transcription.py) regardless — but a
# client that sends `model=gpt-4o-transcribe` should not be rejected for it,
# any more than /v1/chat/completions rejects an unknown chat model name.
_AUDIO_MODEL_ID = transcription.MODEL


@router.post("/audio/transcriptions")
@limiter.limit(PARTNER_RATE_LIMIT)
async def audio_transcriptions(
    request:         Request,
    file:            UploadFile     = File(...),
    model:           str | None     = Form(None),   # noqa: ARG001 - accepted, ignored
    language:        str | None     = Form(None),
    response_format: str            = Form("json"),
    prompt:          str | None     = Form(None),   # noqa: ARG001 - see below
    temperature:     float | None   = Form(None),   # noqa: ARG001 - accepted, ignored
):
    """OpenAI-compatible speech-to-text, so one base URL covers chat and voice.

    `prompt` is accepted and dropped rather than forwarded: transcription.PROMPT
    is what keeps a short, accented clip from being detected as the wrong
    language entirely, and letting a client replace it would reintroduce exactly
    the bug it was added to fix.

    Unlike `/transcribe`, a failure here is an error response, not `{"text": ""}`
    — a generic client has no way to tell an empty transcript from a broken
    backend, and would silently send the empty string on as the visitor's
    question.
    """
    require_partner(request)

    content = await file.read()
    try:
        text = await run_in_threadpool(
            transcription.transcribe, file.filename or "audio.webm", content, language)
    except ValueError as exc:
        raise CompatError(400, str(exc), "invalid_request_error") from exc
    except Exception as exc:
        logger.exception("openai_compat_transcribe_failed")
        raise CompatError(502, f"Transcription failed: {exc}", "api_error") from exc

    logger.info("openai_compat_transcribed", extra={
        "audio_bytes":     len(content),
        "text_len":        len(text),
        "response_format": response_format,
    })

    # `text` and `srt`/`vtt` are served as plain text by the real API; the two
    # JSON shapes differ only in the extra fields verbose_json carries.
    if response_format == "text":
        return PlainTextResponse(text + "\n")
    if response_format == "verbose_json":
        return {"task": "transcribe", "language": language or "", "duration": 0.0, "text": text}
    return {"text": text}


def enabled() -> bool:
    """Whether the compat layer will answer requests — used for startup logging."""
    return configured_partner_key() is not None


# Surface the setting at startup so a deploy that meant to enable this can see
# at a glance that it didn't.
logger.info("openai_compat_enabled" if enabled() else "openai_compat_disabled_no_partner_key")
