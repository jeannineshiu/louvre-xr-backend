"""Shared rate-limiting setup.

This lives in its own module rather than in server.py because two routers need
the same Limiter instance: the visitor endpoints in server.py and the
OpenAI-compatible layer in openai_compat.py. A second Limiter would mean two
independent counter sets over the same Redis/in-memory backend, so a caller
could spend both budgets by alternating endpoints.

Per-IP rate limiting — this backend is publicly reachable for demo/testing and
every OpenAI call (Vision recognition, RAG chat completion, Whisper, TTS) is
billed to a single shared API key, so unbounded public traffic is a cost risk
rather than just a load-testing concern. Limits are per-endpoint since /ask is
the most expensive (Vision + embeddings + chat) and /transcribe is the cheapest.
Tune via the OpenAI dashboard's own hard spending cap as the backstop.

Storage backend: in-memory (the default, one counter dict per process) works
fine for a single Railway replica, but silently stops enforcing anything
meaningful the moment there's more than one — each replica only sees its own
slice of traffic, so N replicas effectively multiplies every limit by N. If
REDIS_URL is set, counters live in Redis instead and are shared across every
replica; if unset, this falls back to the original in-memory behavior so local
dev needs no Redis. in_memory_fallback_enabled=True means a transient Redis
outage degrades to per-instance limiting (same as before Redis was added)
rather than making every request 500.
"""

import hashlib
import hmac
import logging
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Named-partner token. Unset (the default) means the OpenAI-compatible layer is
# switched off entirely — see openai_compat.py. Read from the environment on
# every call rather than captured at import so it can be set per-test.
_PARTNER_KEY_ENV = "PARTNER_API_KEY"

# Anonymous visitors, per IP. The default matches what /ask has always enforced.
ASK_RATE_LIMIT       = os.environ.get("ASK_RATE_LIMIT", "20/hour")
TRANSCRIBE_RATE_LIMIT = os.environ.get("TRANSCRIBE_RATE_LIMIT", "30/hour")
SESSION_RATE_LIMIT   = os.environ.get("SESSION_RATE_LIMIT", "30/hour")

# Named partners integrating a third-party client, per token. Higher than the
# anonymous limit because a partner is a known human testing against a key we
# issued and can revoke, not drive-by public traffic — but still bounded, since
# every call is billed to the same OpenAI key.
PARTNER_RATE_LIMIT = os.environ.get("PARTNER_RATE_LIMIT", "120/hour")


def configured_partner_key() -> str | None:
    """The partner token from the environment, or None when unset/blank."""
    key = os.environ.get(_PARTNER_KEY_ENV, "").strip()
    return key or None


def bearer_token(request: Request) -> str | None:
    """Extract a bearer token from the Authorization header, if present.

    OpenAI-compatible clients send `Authorization: Bearer <key>`, which is what
    the Rokid assistant's optional "API Key" field becomes on the wire.
    """
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def is_partner(request: Request) -> bool:
    """True when the request carries the configured partner token.

    compare_digest keeps the comparison constant-time: this token is the only
    thing standing between the public internet and an endpoint that spends
    money, so it should not be guessable one character at a time.
    """
    expected = configured_partner_key()
    if expected is None:
        return False
    presented = bearer_token(request)
    if presented is None:
        return False
    return hmac.compare_digest(presented, expected)


def client_key(request: Request) -> str:
    """Rate-limit bucket for a request.

    Partner traffic gets its own bucket so a partner testing from a phone on
    mobile data can't burn through the visitor budget shared by everyone else
    behind the same carrier NAT — and vice versa. The token is hashed rather
    than used directly so it never reaches Redis keys or logs in cleartext.
    """
    if is_partner(request):
        digest = hashlib.sha256(bearer_token(request).encode()).hexdigest()[:16]
        return f"partner:{digest}"
    return get_remote_address(request)


_REDIS_URL = os.environ.get("REDIS_URL")
limiter = Limiter(
    key_func=client_key,
    storage_uri=_REDIS_URL or "memory://",
    in_memory_fallback_enabled=bool(_REDIS_URL),
)
logger.info("rate_limit_backend", extra={"backend": "redis" if _REDIS_URL else "memory"})
