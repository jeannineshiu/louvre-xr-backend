# MuseXR Backend

FastAPI backend for **MuseXR**, an AI museum-guide platform for the Louvre. It gives visitors a personal guide — **Sophie** — who recognizes the artwork in front of them from a camera frame or a known exhibit/splat id, and answers questions about it in natural language and voice, grounded in a curated knowledge base rather than open-ended generation. One backend serves three independent, already-shipped frontends: a browser demo, a Meta AI Glasses app, and a multiplayer WebXR tour — so recognition, Q&A, navigation, and voice are built once and stay consistent everywhere visitors encounter the guide.

**Status: Production-ready.** Feature-complete and live across all three client frontends, deployed on Railway with automatic redeploy on push to `main`. This isn't just "it works" — every change to `main` passes through an automated eval harness, a 40-case unit test suite, dependency vulnerability scanning, and a stale-index check before it can merge; production itself is covered by error tracking and rate limiting that holds up across multiple replicas. See [Production Readiness](#production-readiness) for the full picture.

Core exhibition: **Louvre Museum, Paris** — eight sculptures spanning antiquity to the 19th century, plus four supplementary works (Jardin des Tuileries and a Sydney field-demo piece) that support the full feature set outside the main museum building.

> **Access:** This server is deployed on Railway. Contact a team member for the public URL — it is not published here to limit access to the team.

---

## Contents

- [Overview](#overview)
- [Production Readiness](#production-readiness)
- [Frontends](#frontends)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Knowledge Base](#knowledge-base)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [OpenAI-Compatible API](#openai-compatible-api)
- [Context-Aware Response Length (optional)](#context-aware-response-length-optional)
- [Sculpture Recognition](#sculpture-recognition)
- [Splat Identification](#splat-identification)
- [Multi-User / WebXR Integration](#multi-user--webxr-integration)
- [Conversation History](#conversation-history)
- [Deployment](#deployment)
- [Tech Stack](#tech-stack)

---

## Overview

This is a **pure QA + routing service** — no sensors, no camera, no background threads. It receives a request, resolves which exhibit is being discussed, retrieves grounded knowledge, and returns an answer.

1. **Identify** the exhibit — from an `exhibit` id, a `splat` identifier, or an uploaded photo (GPT-4o Vision), in that priority order. If none is supplied, the answer still works, just without an anchored exhibit.
2. *(Optional)* **Pick a response length** if the frontend supplies visitor context (gaze duration, crowd level) — see [Context-Aware Response Length](#context-aware-response-length-optional). Otherwise every answer defaults to full length.
3. **Answer** the question via a RAG pipeline (FAISS vector search + GPT-4o), grounded in the exhibit's knowledge base, prompted for the chosen length, and aware of the full conversation history for follow-ups

Any environment sensing (camera capture, gaze tracking, crowd/noise estimation) happens entirely on the client; this server only consumes the values passed in the request body.

## Production Readiness

This service went through a deliberate hardening pass beyond initial feature delivery — the same rigor expected of any customer-facing backend, applied to the specific failure modes of an LLM/RAG system. The engineering checklist and lessons behind it are written up in [`docs/RAG_SKILLS.md`](docs/RAG_SKILLS.md); the summary:

- **Quality gate on every PR, not just code review.** A golden-set eval harness (`eval/`, 30 cases) runs deterministic checks — retrieval hit, length budget, required/forbidden content — as a required CI check on every PR into `main`; a separate scheduled job runs an LLM-judge pass for deeper groundedness scoring. A prompt or retrieval change that degrades answer quality is caught before merge, not discovered by a visitor.
- **40 unit tests, evaluated before a single API dollar is spent.** Router, splat registry, cache, navigation lookup, exact-match retrieval, and chit-chat routing are all covered by pytest, run first in CI so a broken build fails fast and free.
- **Hardened dependency supply chain.** `requirements.txt` is a fully hash-pinned lockfile (`pip-tools --generate-hashes`), installed with `--require-hashes` in both CI and the Docker build; `pip-audit` and Dependabot scan for known CVEs on every PR.
- **Deterministic guardrails instead of LLM guesswork.** Navigation, exact-name lookups, and chit-chat are resolved by plain code paths — not left for the LLM to infer — which is cheaper, faster, and immune to hallucination on exactly the questions (room numbers, proper nouns) where a wrong guess is most visible to a visitor.
- **Stale-index protection.** CI fails the PR if the committed FAISS index doesn't match the current knowledge base and chunking schema (`rag_engine.py --check-fresh`), closing off a class of bugs where local testing passes against one index while production silently serves another.
- **Production observability.** Sentry (opt-in via `SENTRY_DSN`) captures every unhandled exception and `logger.exception` call automatically, with `send_default_pii=False` enforced — errors are tracked without ever logging visitor questions, answers, or other PII.
- **Rate limiting that survives horizontal scaling.** The per-IP limiter is Redis-backed when `REDIS_URL` is set, so limits hold across replicas instead of resetting per-process; it degrades gracefully to in-memory limiting if Redis is unavailable, rather than failing requests.

## Frontends

This backend is shared by three independent clients. The knowledge base and recognition cover all 12 exhibits — which subset each client actually surfaces is a frontend-side choice, not a backend limitation.

| Client | Experience | Exhibits it uses |
|---|---|---|
| `demo.html` (this repo, `GET /demo`) | On-site Louvre visit — browser fallback when a headset isn't available | All 8 main Louvre exhibits, via camera scan |
| [MuseXR-Android](https://github.com/jeannineshiu/MuseXR-Android) | On-site Louvre visit — Android app for **Meta AI Glasses**: look at a sculpture, tap the glasses, hear an AI-generated description spoken back through them | All 8 main Louvre exhibits, via camera scan |
| [WebXR](https://webxr-worldmodels.vercel.app) | Remote multiplayer WebXR tour | Only the 3 Jardin des Tuileries Gaussian splats — see [Splat Identification](#splat-identification) |

MuseXR-Android is built on the **Meta Wearables Device Access Toolkit (DAT)** for pairing with the glasses and pulling frames from their camera; from this backend's point of view it's just another `POST /ask` caller sending `image_base64`, indistinguishable from `demo.html`'s requests.

The WebXR frontend's default scene is the Jardin des Tuileries, not the Louvre building, so its Sophie guide only needs to recognize the three Maillol splats there (`Air`, `La Nuit`, `L'Hommage à Cézanne`). That scoping is encoded in `splat_mapping.json`'s aliases on the frontend-facing side — the underlying `/ask`, `/splats`, and image-recognition endpoints can resolve any of the 12 exhibits regardless of which client calls them.

## Architecture

```
Client (Browser / WebXR / Phone)
  ├── captures a camera frame or holds a known exhibit/splat id   (optional)
  ├── tracks gaze_duration / crowd for response-length tuning     (optional)
  ├── maintains conversation history array (client-side)
  └── sends POST /ask
            ↓
AI Server (this repo)
  ├── Resolve exhibit   → exhibit id | splat id | image (GPT-4o Vision), in that priority order
  ├── Pick response mode → explicit `mode` > Context Router (if `state` supplied) > default FULL_VOICE
  ├── RAG Engine        → FAISS retrieval + GPT-4o answer, prompted for the chosen mode (with history)
  └── returns { mode, answer, exhibit }
```

---

## Project Structure

```
louvre-ar-backend/
│
├── server.py               # FastAPI app — main entry point
├── openai_compat.py        # OpenAI-compatible /v1 layer for third-party chat clients
├── rate_limit.py           # Shared slowapi limiter + partner-key buckets
├── qa_pipeline.py          # Orchestrates all modules in order
├── context_router.py       # Optional response-length routing from gaze_duration + crowd
├── rag_engine.py           # RAG: FAISS vector store + GPT-4o, mode-specific prompts
├── exhibit_recognizer.py   # GPT-4o Vision: identify sculpture from camera frame
├── exhibits_data.py        # Museum knowledge base (12 sculptures: 8 main + 4 supplementary, 6 sections each)
├── navigation_routes.py    # Direct (from_id, to_id) route lookup table — 56 routes, no FAISS
├── splat_registry.py       # Resolves a Gaussian-splat identifier to an exhibit (GET /splats)
├── splat_mapping.json      # Editable splat → exhibit alias table used by splat_registry.py
├── tts.py                  # Sophie's voice — OpenAI TTS, saves mp3s to temp_audio/
│
├── faiss_index/            # Pre-built FAISS vector index (committed — rebuild after editing exhibits_data.py)
│   ├── index.faiss
│   ├── index.pkl
│   └── source_hash.txt     # Hash of exhibits_data.py + chunking schema; CI fails the PR if this is stale
├── temp_audio/             # Generated Sophie TTS mp3s, served at GET /audio/{file_id}
│
├── demo.html               # Browser demo — voice chat UI served at GET /demo
├── Dockerfile              # Container image for the FastAPI server
├── requirements.txt
└── .env.example             # API key template — copy to .env and fill in
```

---

## Knowledge Base

### Louvre Museum — Main Exhibits

Eight sculptures displayed inside the Louvre museum building, spanning antiquity to the 19th century. These are the primary works of the XR experience, with full knowledge sections, navigation data, and Louvre boutique shop information.

| Sculpture | Artist | Date | Location |
|---|---|---|---|
| Winged Victory of Samothrace | Unknown (Rhodian school) | c. 190 BC | Salle 703, Denon — Daru Staircase, Level 1 |
| Venus de Milo | Attr. Alexandros of Antioch | c. 130–100 BC | Salle 345, Sully — Galerie de Milo, Level 0 |
| Cupid and Psyche | Antonio Canova | 1793 | Salle 403, Denon — Michelangelo Gallery, Level 0 |
| The Borghese Gladiator | Agasias of Ephesus | c. 100 BC | Salle 348, Sully — Greek Antiquities, Level 0 |
| The Dying Slave | Michelangelo | 1513–16 | Salle 403, Denon — Michelangelo Gallery, Level 0 |
| The Seated Scribe | Unknown (Egyptian Old Kingdom) | c. 2620–2500 BC | Salle 635, Sully — Egyptian Antiquities, Level 1 |
| Bastet Cat Statue | Unknown (Egyptian Late Period) | c. 664–332 BC | Salle 630, Sully — Egyptian Antiquities, Level 1 |
| La Siesta | Denis Foyatier | 1848 | Salle 225, Richelieu — Modern Sculpture, Level 0 |

Each main exhibit has six structured knowledge sections: `key_facts`, `visual_description`, `historical_context`, `technique`, `story`, `shop`.

**Navigation** is handled separately via `navigation_routes.py` — a direct `(from_id, to_id)` lookup table with 56 pre-written routes covering all pairs of main exhibits. Navigation does not go through FAISS or GPT-4o: the frontend detects a navigation question, resolves the destination exhibit, and calls `GET /navigate` directly for a deterministic, instant response.

### Supplementary Exhibits

Four additional works extend the knowledge base beyond the core Louvre building — used for the Tuileries WebXR scene and an off-site field demo. They support the full feature set (text/voice Q&A, image recognition, shop info where available) but have no navigation data between them and the main exhibits.

| Sculpture | Artist | Date | Location |
|---|---|---|---|
| Air | Aristide Maillol | 1938 | Jardin des Tuileries, Paris |
| La Nuit (Night) | Aristide Maillol | 1902–1909 | Jardin des Tuileries, Paris |
| L'Hommage à Cézanne | Aristide Maillol | 1912 | Jardin des Tuileries (Carrousel Garden), Paris |
| Miles Franklin Statue | Jacek Luszczyk | 2003 | MacMahon Street, Hurstville, Sydney |

---

## Getting Started

```bash
git clone <repo-url>
cd louvre-ar-backend

conda create -n contextar python=3.10
conda activate contextar
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in OPENAI_API_KEY

uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The FAISS index is pre-built and committed — no rebuild needed for local development.

`requirements.txt` is a fully pinned, hash-verified lockfile generated from `requirements.in` with
[pip-tools](https://github.com/jazzband/pip-tools). To add/upgrade a dependency, edit `requirements.in`
and regenerate:

```bash
pip install pip-tools
pip-compile --generate-hashes --output-file=requirements.txt requirements.in
```

CI and the Docker build both install with `pip install --require-hashes -r requirements.txt`, so a
regenerated lockfile is required whenever `requirements.in` changes.

| Resource | URL |
|---|---|
| Server | `http://localhost:8000` |
| Interactive API docs (Swagger) | `http://localhost:8000/docs` |
| Browser demo | `http://localhost:8000/demo` |

---

## API Reference

### `POST /ask`

The core Q&A endpoint. Resolves the exhibit, retrieves grounded knowledge, and returns an answer.

**Rate limit:** 20 requests/hour per IP. Exceeding it returns HTTP `429`. See [API Usage Limits](#api-usage-limits).

**Request fields**

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `string` | Yes | Visitor's natural-language question. Must be non-empty — returns 422 if blank. |
| `exhibit` | `string` | No | The exhibit the visitor is currently facing, as an id (`hommage_a_cezanne_maillol`) or display name (`L'Hommage à Cézanne`). Use when the frontend already knows the exhibit (e.g. a preset WebXR splat) so Sophie answers correctly without a camera scan. Highest priority — if set, recognition is skipped entirely. |
| `splat` | `string` | No | Identifier of the currently displayed Gaussian splat (filename, URL, slug, or short name). Resolved to an exhibit automatically — see [Splat Identification](#splat-identification). Used only if `exhibit` isn't set; also skips image recognition if it resolves. |
| `image_base64` | `string` | No | Base64 JPEG/PNG. GPT-4o Vision identifies the sculpture — but **only runs if neither `exhibit` nor `splat` resolved to a known exhibit.** Lowest priority of the three. |
| `mode` | `string` | No | Direct override — skips the context router entirely. One of `GLANCE_CARD` \| `BRIEF_TEXT` \| `FULL_VOICE` \| `BRIEF_TEXT_PROMPT` \| `NAVIGATION` \| `SHOP`. Takes priority over `state`. Any other value returns 422. |
| `state` | `object` | No | Optional visitor-context signal for automatic response-length routing — see [Context-Aware Response Length](#context-aware-response-length-optional). Omit entirely for a standard full-length answer. |
| `history` | `array of {role, content}` | No | Prior conversation turns. `role` must be `"user"` or `"assistant"` — returns 422 otherwise. See [Conversation History](#conversation-history). |
| `voice` | `boolean` | No | Default `false`. If `true`, generates a Sophie TTS audio file and returns `audio_url`. |
| `asker_name` | `string` | No | Name of the asker, used with `participants` for multi-user rooms — see [Room context](#room-context--multi-user-qa). |
| `participants` | `array of string` | No | Everyone currently in the room, e.g. `["Alice", "Bob", "Charlie"]`. |

**Priority for response length:** `mode` (if set) → `state` (if set) → default `FULL_VOICE`.

`NAVIGATION` and `SHOP` are RAG-backed modes tuned for directions-only or merchandise-only answers, respectively — distinct from the deterministic `GET /navigate` lookup. The context router never selects them automatically; they're only reachable via an explicit `mode` value.

**Response fields**

| Field | Notes |
|---|---|
| `mode` | Response mode used: `NO_RESPONSE` \| `BRIEF_TEXT` \| `GLANCE_CARD` \| `FULL_VOICE` \| `BRIEF_TEXT_PROMPT`, or the `NAVIGATION`/`SHOP` value passed in, if any |
| `answer` | Text answer; empty string when `mode` is `NO_RESPONSE` |
| `exhibit` | Resolved sculpture name; empty string if not identified |
| `audio_url` | Full HTTPS URL of the generated mp3. Only present when `voice: true`. |

**Example**

```bash
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Venus de Milo"}'
```

```json
{ "mode": "FULL_VOICE", "answer": "The Venus de Milo is a marble sculpture...", "exhibit": "" }
```

#### Room context — multi-user Q&A

When **both** `asker_name` and `participants` are provided, the server prepends a context line to the question before sending it to GPT-4o, so Sophie can address the group by name (e.g. *"Great question, Alice — for everyone here…"*) instead of an anonymous visitor. Both fields are optional and independent of `voice`/`mode`/`state` — omitting either leaves the question unchanged.

```bash
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Winged Victory", "voice": true, "asker_name": "Alice", "participants": ["Alice", "Bob", "Charlie"]}'
```

---

### `POST /transcribe`

Speech-to-text for voice questions. The frontend records audio with `MediaRecorder` and posts the blob here; the server forwards it to **OpenAI Whisper** (`whisper-1`) and returns the transcript. Used by both the multi-user WebXR flow and `demo.html`'s mic input — Whisper detects the spoken language directly from the audio instead of relying on the browser's `SpeechRecognition`, which has no real language auto-detection.

**Rate limit:** 30 requests/hour per IP. Exceeding it returns HTTP `429`. See [API Usage Limits](#api-usage-limits).

**Request:** `multipart/form-data`

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file (audio blob) | Yes | Recorded audio — `webm` or `mp4`/`m4a`. |

**Response:** `{ "text": "Tell me about the Winged Victory" }`

On any failure (invalid/empty audio, Whisper API error) the endpoint returns `{"text": ""}` with HTTP **200** — never a 500 — so the client can degrade gracefully. A missing `file` field returns 422.

```bash
curl -X POST <BASE_URL>/transcribe -F "file=@recording.webm;type=audio/webm"
```

---

### `GET /navigate`

Direct walking-directions lookup — no FAISS, no LLM, instant dictionary lookup.

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `from_exhibit` | `string` | Yes | Exhibit id of the visitor's current location |
| `to_exhibit` | `string` | Yes | Exhibit id of the destination |

**Exhibit IDs**

| Exhibit | ID |
|---|---|
| Winged Victory of Samothrace | `winged_victory_of_samothrace` |
| Venus de Milo | `venus_de_milo` |
| Cupid and Psyche | `cupid_and_psyche` |
| The Borghese Gladiator | `borghese_gladiator` |
| The Dying Slave | `the_dying_slave` |
| The Seated Scribe | `the_crouching_scribe` |
| Bastet Cat Statue | `bastet_cat_statue` |
| La Siesta | `la_siesta_foyatier` |

```bash
curl "<BASE_URL>/navigate?from_exhibit=venus_de_milo&to_exhibit=the_crouching_scribe"
```

```json
{
  "found": true,
  "directions": "Head north through the Sully wing and take the stairs to Level 1...",
  "from_name": "Venus de Milo",
  "to_name": "The Seated Scribe"
}
```

If `from_exhibit == to_exhibit`, returns `"You are already at [name]."`. If no route exists, returns `{ "found": false, "directions": "" }`.

---

### `GET /splats`

Registry lookup for the Gaussian-splat resolver — see [Splat Identification](#splat-identification) for the full mapping behaviour.

```bash
curl "<BASE_URL>/splats?value=cezanne_v2.splat"
# → { "value": "cezanne_v2.splat", "exhibit": "L'Hommage à Cézanne", "recognized": true }

curl "<BASE_URL>/splats"   # full alias → exhibit-name mapping
```

---

### `POST /session/start`

Generates Sophie's welcome greeting (one short sentence, max ~20 words) when visitors join a shared WebXR room. Call once per room entry and broadcast the result to all members.

**Rate limit:** 30 requests/hour per IP. Exceeding it returns HTTP `429`. See [API Usage Limits](#api-usage-limits).

| Field | Type | Required | Notes |
|---|---|---|---|
| `exhibit` | `string` | No | Exhibit name, if already known — Sophie references it in the greeting. |
| `voice` | `boolean` | No | Default `false`. If `true`, returns `audio_url`. |

**Response:** `{ "greeting": "...", "audio_url": "..." }` (`audio_url` only when `voice: true`)

```bash
curl -X POST <BASE_URL>/session/start \
  -H "Content-Type: application/json" \
  -d '{"exhibit": "Venus de Milo", "voice": true}'
```

---

### `GET /audio/{file_id}`

Serves a previously generated Sophie TTS mp3 (the file behind an `audio_url` returned by `/ask` or `/session/start`). Returns 404 if the file doesn't exist. Files live under `temp_audio/` with no automatic cleanup — see the storage note under [Multi-User / WebXR Integration](#multi-user--webxr-integration).

### `GET /demo`

Returns the browser demo page (`demo.html`) — see [Multi-User / WebXR Integration](#multi-user--webxr-integration).

### `GET /health`

`{ "status": "ok" }` — liveness check.

---

## API Usage Limits

`/ask`, `/transcribe`, and `/session/start` each call OpenAI (GPT-4o Vision, RAG chat completion, Whisper, or TTS), billed to a single shared `OPENAI_API_KEY`. Since this backend is reachable by the public for demo/testing, each of those endpoints is rate-limited **per client IP** to cap cost exposure:

| Endpoint | Limit |
|---|---|
| `POST /ask` | 20 requests/hour |
| `POST /transcribe` | 30 requests/hour |
| `POST /session/start` | 30 requests/hour |
| `GET /tts-debug` | 5 requests/hour |
| `POST /v1/chat/completions` | 120 requests/hour, per partner key (see [OpenAI-Compatible API](#openai-compatible-api)) |

Each limit can be overridden per deploy with `ASK_RATE_LIMIT`, `TRANSCRIBE_RATE_LIMIT`, `SESSION_RATE_LIMIT`, and `PARTNER_RATE_LIMIT` (slowapi syntax, e.g. `60/hour`); the table shows the defaults.

Requests carrying a valid `PARTNER_API_KEY` are counted per key rather than per IP, so a named integrator testing over mobile data can't drain the visitor budget shared by everyone else behind the same carrier NAT — or be drained by them.

Exceeding a limit returns HTTP `429`; the frontend should treat this as "try again later" rather than a hard error. Limits are enforced via [slowapi](https://github.com/laurentS/slowapi) with a pluggable storage backend, controlled by `REDIS_URL`:

- **Unset (default):** in-memory counters — fine for a single Railway replica/worker, but each process counts independently, so scaling to N replicas effectively multiplies every limit by N.
- **Set:** counters live in Redis instead, shared across every replica — the limits in the table above hold regardless of replica count. A transient Redis outage degrades gracefully back to per-instance in-memory limiting (`in_memory_fallback_enabled=True`) rather than 500ing every request.

This repo doesn't provision Redis itself — add a Redis instance (e.g. Railway's Redis plugin) and set `REDIS_URL` if/when this service runs more than one replica.

These limits are a backstop, not a substitute for capping spend on the OpenAI key itself — set a hard spending limit on `OPENAI_API_KEY` in the [OpenAI dashboard](https://platform.openai.com/settings/organization/limits).

---

## OpenAI-Compatible API

Third-party glasses clients — [RokidAIAssistant](https://github.com/zero2005x/RokidAIAssistant) and anything else with a "custom endpoint" box — speak the OpenAI chat protocol and nothing else. They take a **base URL**, append `chat/completions` to it, POST `{model, messages}`, and often call `GET /v1/models` first to populate a model picker.

`/ask` doesn't speak that protocol: it has its own schema and picks the model server-side. Pointing such a client at `https://<host>/ask` makes it request `https://<host>/ask/chat/completions` → **404**, no matter what model name is typed. `/v1` exists to bridge that gap.

**Client setup**

| Field | Value |
|---|---|
| Base URL | `https://<host>/v1/` |
| Model | `louvre-sophie` (any string works — the value is ignored) |
| API Key | the deploy's `PARTNER_API_KEY` |
| Protocol | Chat Completions (not Responses) |

```bash
curl https://<host>/v1/chat/completions \
  -H "Authorization: Bearer $PARTNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "louvre-sophie", "messages": [{"role": "user", "content": "Who made the Winged Victory?"}]}'
```

**What it does and doesn't carry**

- The **last `user` message** becomes the question; earlier `user`/`assistant` turns become conversation history, the same way `/ask` accepts `history`.
- **Camera frames survive.** A vision content part (`{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`) is unpacked into the pipeline's image input, so sculpture recognition works here too. Remote `http(s)` image URLs are ignored rather than fetched.
- **`system` messages are dropped.** Sophie's persona and grounding rules come from the RAG prompt; honouring a caller-supplied system prompt would let any client with the token restyle or jailbreak the guide.
- **`stream: true` is supported.** The pipeline returns a finished string, so the stream is a protocol formality (role frame → content frame → finish frame → `[DONE]`) rather than token-by-token — but a client that asks for SSE and gets a plain JSON body hangs until timeout, which is far harder to diagnose than a fast stream.
- **Sampling parameters are accepted and ignored** (`temperature`, `max_tokens`, `top_p`, …). Generation settings are fixed in `rag_engine.py`.
- **Museum-specific fields aren't exposed** — `mode`, `state` routing, `voice`/`audio_url`, `exhibit`, `splat`. A generic chat client has nowhere to put them; use `/ask` for those.

**Access control.** `/v1/*` is off unless `PARTNER_API_KEY` is set, and returns `503` with the reason when it isn't — an unauthenticated `/v1/chat/completions` on a public host is actively scanned for, and every call spends real money on the shared `OPENAI_API_KEY`. Errors use OpenAI's `{"error": {"message": ...}}` shape, because clients render that string and show nothing useful for anything else.

## Context-Aware Response Length (optional)

The server can adjust answer length automatically based on visitor context (`gaze_duration`, `crowd`), but **this is a secondary, opt-in feature** — it exists to support richer XR clients, not a requirement of the core product. A frontend can ignore it entirely by omitting `state`, in which case every answer defaults to the full-length `FULL_VOICE` mode.

If a client does supply `state`, the routing logic is:

| `gaze_duration` | `crowd` | Mode | Target length |
|---|---|---|---|
| < 5s | any | `NO_RESPONSE` | — (do not interrupt) |
| 5–15s | crowded | `GLANCE_CARD` | ~20 words |
| 5–15s | low | `BRIEF_TEXT` | ~50 words |
| ≥ 15s | crowded | `BRIEF_TEXT_PROMPT` | ~60 words, nudges toward a quieter spot |
| ≥ 15s | low | `FULL_VOICE` | ~100 words |

`state.noise` is accepted for forward compatibility but currently has no effect on routing — audio is delivered through earphones, so ambient noise doesn't change the response strategy.

`mode` can also be set directly on `/ask` to bypass this router entirely and force a specific response length, independent of `state`.

---

## Sculpture Recognition

The server has no camera — recognition only runs when the client includes `image_base64` in the request.

```
Client captures one frame → base64 JPEG → POST /ask
Server calls GPT-4o Vision (~1–3s)
Returns { exhibit: "Venus de Milo", ... }
```

This is intentionally a single call per interaction, not frame-by-frame streaming: GPT-4o Vision's 1–3s latency makes continuous polling impractical. Recommended pattern — trigger one capture when the visitor's gaze crosses a few seconds of dwell time, then reuse the returned `exhibit` for the rest of that interaction.

GPT-4o Vision requires all listed visual markers to be clearly visible before returning a sculpture name; ambiguous images return `"unknown"`. When recognition fails, the server returns an explicit message naming the works it covers rather than guessing:

> *"I wasn't able to identify this sculpture as one of the works in my system. I can tell you about: the Winged Victory of Samothrace, Venus de Milo, …"*

---

## Splat Identification

The [WebXR scene](https://webxr-worldmodels.vercel.app) simulates the Jardin des Tuileries and contains three Gaussian-splat sculptures, all by **Aristide Maillol**:

| Splat | Exhibit id | Notes |
|---|---|---|
| Air | `air_maillol` | Default splat shown on load |
| La Nuit (Night) | `la_nuit_maillol` | |
| L'Hommage à Cézanne | `hommage_a_cezanne_maillol` | |

The frontend sends the current splat's identifier as the `splat` field on `POST /ask`, and the backend resolves it to an exhibit — so a question with no visual cues (*"What is this?"*) still anchors to the correct sculpture instead of the RAG guessing from question text alone.

The resolver is deliberately forgiving: it accepts exhibit ids, display names, filenames (`air_2024.ply`), slugs (`air`), or full URLs (`https://.../splats/air.splat`); ignores case, accents, and punctuation; and strips known splat extensions (`.splat` / `.ply` / `.ksplat` / `.spz`). Unrecognised identifiers resolve to nothing rather than erroring — the question is simply answered without an anchored exhibit.

New aliases can be added to `splat_mapping.json` without a code change or logic redeploy. Use `GET /splats?value=<what your frontend sends>` to confirm resolution before wiring a new splat into `/ask`.

---

## Multi-User / WebXR Integration

Built for [webxr-worldmodels.vercel.app](https://webxr-worldmodels.vercel.app) using IWSDK and Netblocks multiplayer. Sophie acts as a shared tour guide — when anyone asks a question, everyone in the room hears the answer simultaneously.

```
Any user speaks → record blob → POST /transcribe → { text }
                                       ↓
        POST /ask (voice: true, asker_name, participants)
                                       ↓
              Backend: RAG answer + OpenAI TTS
                                       ↓
                     { answer, audio_url }
                                       ↓
         Frontend: Netblocks broadcast audio_url
                                       ↓
          All room members fetch URL → play audio
```

```javascript
// Room entry
async function onRoomJoin(currentExhibit = null) {
  const body = { voice: true, ...(currentExhibit && { exhibit: currentExhibit }) };
  const resp = await fetch(`${BASE_URL}/session/start`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const { audio_url } = await resp.json();
  if (audio_url) netblocksRoom.broadcast({ type: 'sophie_audio', url: audio_url });
}

// Q&A
async function askSophie(question) {
  const resp = await fetch(`${BASE_URL}/ask`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, mode: 'FULL_VOICE', voice: true }),
  });
  const data = await resp.json();
  showSubtitle(data.answer);
  if (data.audio_url) netblocksRoom.broadcast({ type: 'sophie_audio', url: data.audio_url });
}

netblocksRoom.on('sophie_audio', ({ url }) => new Audio(url).play());
```

Sophie's voice is generated with **OpenAI TTS** (`gpt-4o-mini-tts`, `nova` by default) — a natively multilingual model, chosen over the older `tts-1`/`tts-1-hd` because those read non-English text with an English accent instead of switching pronunciation. Configurable via the `SOPHIE_VOICE` environment variable (`alloy` \| `echo` \| `fable` \| `onyx` \| `nova` \| `shimmer`). `audio_url` is a full HTTPS URL fetchable by all room members without a proxy; audio files are stored temporarily on the server (consider S3 or similar for a larger-scale deployment). Native clients (e.g. MuseXR-Android) are not subject to CORS.

### Demo web app (`demo.html`)

A single-page voice chat UI served directly by this backend at `GET /demo` — a browser fallback when a headset isn't available, no app install required.

| Feature | Description |
|---|---|
| Sculpture scan | Camera capture → GPT-4o Vision identifies the sculpture and gives a one-line intro |
| Voice input / output | `POST /transcribe` (OpenAI Whisper) for input, `POST /ask`'s `audio_url` (OpenAI `gpt-4o-mini-tts`) for output — both server-side and genuinely multilingual. Browser `speechSynthesis` is kept only as a fallback if `audio_url` is missing or playback errors out. |
| Multi-turn conversation | Full history maintained per sculpture session; follow-ups resolve correctly |
| Shop info | Purchase-related questions surface real [Louvre boutique](https://boutique.louvre.fr) products |
| Navigation | Ask "How do I get to the Venus de Milo?" — resolved client-side and answered via `GET /navigate`, or via the `NAVIGATION` RAG mode when the destination can't be parsed |
| Multilingual | Whisper detects the spoken language directly from the audio (no browser-language guessing); the AI answer and its TTS audio both come back in that language |

**Browser support:** Safari and Chrome (iPhone/Android/Desktop) all support camera and playback of the server's TTS audio; voice *input* needs `MediaRecorder` + microphone access (all evergreen mobile/desktop browsers) and HTTPS (localhost is exempt).

**Officially supported languages: English, French, German, Chinese (Mandarin).** These are the only languages calibrated end-to-end — `rag_engine._PERSONA_GUIDE` names them explicitly, `qa_pipeline._CHITCHAT_REPLIES` has canned greetings/thanks/bye in all four, `eval/golden_set.jsonl` has cross-lingual regression cases for each, and `demo.html`'s `NAV_KEYWORDS`/`SHOP_KEYWORDS` cover all four. Whisper (STT) and `gpt-4o-mini-tts` (TTS) both support many more languages than this at the model level, and the RAG persona will attempt to answer in whatever language it detects — but only these four have a calibrated retrieval threshold (`eval/calibrate_threshold.py`) and dedicated eval coverage, so anything else is best-effort, not guaranteed. Navigation directions from the static lookup table are always in English regardless of the visitor's language; UI chrome (badges, error prompts) also stays in English.

### CORS

Browser requests are restricted to an explicit origin allow-list in `server.py`:

| Origin | Purpose |
|---|---|
| `https://webxr-worldmodels.vercel.app` | Production WebXR frontend |
| `http://localhost:3000`, `http://localhost:5173` (and `127.0.0.1`) | Local frontend development |
| `https://localhost:8081` | Local HTTPS dev server (HTTPS required for camera/mic) |

All methods/headers are allowed and credentialed requests are enabled. Add any new frontend origin (e.g. a Vercel preview URL) to `ALLOWED_ORIGINS` in `server.py`.

---

## Conversation History

The server is stateless — the client owns and sends the conversation history with each request, so follow-ups like *"What technique did he use?"* resolve without the visitor repeating context.

Each turn, the client appends the question and answer to a local history array and includes the full array on the next request:

```json
{
  "question": "What technique did he use?",
  "history": [
    { "role": "user",      "content": "Who made the Dying Slave?" },
    { "role": "assistant", "content": "The Dying Slave was carved by Michelangelo between 1513 and 1516." }
  ]
}
```

`history` is optional — omit it for the first question of a session. Clear it client-side when the visitor moves to a new sculpture; there is no server-side session state, so a restarted app simply starts a fresh array.

---

## Deployment

Deployed on Railway via the included `Dockerfile`; redeploys automatically on every push to `main`.

| Environment variable | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`) |
| `SENTRY_DSN` | Optional — enables error tracking (see below). Unset = disabled. |
| `SENTRY_ENVIRONMENT` | Optional, default `production` |
| `SENTRY_TRACES_SAMPLE_RATE` | Optional, default `0.1` |
| `REDIS_URL` | Optional — shares rate-limit counters across replicas (see [API Usage Limits](#api-usage-limits)). Unset = in-memory, per-replica. |
| `PARTNER_API_KEY` | Optional — enables the [OpenAI-compatible API](#openai-compatible-api) and acts as its bearer token. Unset = `/v1/*` returns 503. |
| `ASK_RATE_LIMIT` etc. | Optional — override the default rate limits (see [API Usage Limits](#api-usage-limits)). |

Since this backend is publicly reachable, set a hard spending limit on `OPENAI_API_KEY` in the OpenAI dashboard before sharing the URL — the per-IP rate limits in this repo (see [API Usage Limits](#api-usage-limits)) reduce but don't eliminate cost exposure from public traffic.

### Error tracking (Sentry)

Set `SENTRY_DSN` (from sentry.io → Project Settings → Client Keys) to enable [Sentry](https://sentry.io) error
tracking — unhandled exceptions in any request (e.g. `/ask`'s pipeline failures) are reported automatically via
the FastAPI integration, and everywhere this codebase already calls `logger.exception(...)` (RAG/vision/TTS
failure paths) is picked up too, since Sentry's logging integration captures any `ERROR`-level log call. No code
changes needed to add a new reported error path — just use `logger.exception(...)` as the rest of the codebase
does. `send_default_pii=False` is set explicitly: Sentry gets the exception and traceback, never visitor
question/answer text (see the note in `server.py`'s `/ask` handler on why that's never logged either). Leave
`SENTRY_DSN` unset for local development — Sentry is a complete no-op without it.

Rebuild the FAISS index only after editing `exhibits_data.py`:

```bash
python rag_engine.py --build
git add faiss_index/
git commit -m "Rebuild FAISS index"
git push origin main
```

The `eval` CI workflow runs `python rag_engine.py --check-fresh` on every PR into `main` and fails fast (no OpenAI calls) if `exhibits_data.py` or the chunking logic in `rag_engine.py` changed without a corresponding index rebuild+commit.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API server | FastAPI + Uvicorn |
| LLM | GPT-4o (QA + Vision) |
| Speech-to-text | OpenAI Whisper (`whisper-1`) — `POST /transcribe` |
| Text-to-speech | OpenAI TTS (`gpt-4o-mini-tts`, Sophie voice) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector search | FAISS (via LangChain) |
| Image processing | OpenCV |
| Deployment | Railway (Docker) |
