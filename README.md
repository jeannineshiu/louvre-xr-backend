# Louvre XR Backend

FastAPI backend for an XR museum companion system.
Exhibition: **Louvre Museum & Jardin des Tuileries, Paris** — eight iconic sculptures from antiquity to the 20th century.

> **Access:** This server is deployed on Railway. Contact a team member for the public URL — it is not published here to limit access to the team.

---

## What This Server Does

This is a **pure QA + routing service**. It has no sensors, no camera, and no background threads. All it does is:

1. **Receive** a visitor's question + optional context (sensor state, camera image) from the frontend
2. **Identify** the sculpture in the image (if provided), using GPT-4o Vision
3. **Decide** the appropriate response mode based on the visitor's context (gaze duration, crowd level)
4. **Answer** the question using a RAG pipeline (FAISS vector search + GPT-4o), with a prompt tuned to the selected mode

Everything that involves sensing the physical environment — gaze tracking, crowd detection, noise classification — happens on the XR device and is passed to this server as values in the request body.

```
XR Device (Unity / Quest / Phone / Browser)
  ├── measures gaze_duration, crowd, noise
  ├── captures camera frame (optional)
  └── sends POST /ask
            ↓
AI Server (this repo)
  ├── Step 1: GPT-4o Vision → identify sculpture (if image provided)
  ├── Step 2: Context Router → decide mode from sensor state
  ├── Step 3: RAG Engine → FAISS retrieval + GPT-4o answer
  └── returns { mode, answer, exhibit }
```

---

## Project Structure

```
louvre-ar-backend/
│
├── server.py               # FastAPI app — main entry point
├── qa_pipeline.py          # Orchestrates all modules in order
├── context_router.py       # Decides response mode from gaze_duration + crowd + noise
├── rag_engine.py           # RAG: FAISS vector store + GPT-4o, mode-specific prompts
├── exhibit_recognizer.py   # GPT-4o Vision: identify sculpture from camera frame
├── exhibits_data.py        # Museum knowledge base (8 sculptures, 5 sections each)
│
├── faiss_index/            # Pre-built FAISS vector index (committed — no rebuild needed)
│   ├── index.faiss
│   └── index.pkl
│
├── Dockerfile              # Container image for the FastAPI server
├── requirements.txt
└── .env.example            # API key template — copy to .env and fill in
```

---

## The Eight Sculptures

| Sculpture | Artist | Date | Location |
|---|---|---|---|
| Winged Victory of Samothrace | Unknown (Rhodian school) | c. 190 BC | Salle 703, Daru Staircase |
| Venus de Milo | Attr. Alexandros of Antioch | c. 130–100 BC | Salle 346 |
| Cupid and Psyche | Antonio Canova | 1793 | Salle 403, Richelieu Wing |
| The Borghese Gladiator | Agasias of Ephesus | c. 100 BC | Salle 348 |
| The Dying Slave | Michelangelo | 1513–16 | Salle 403, Richelieu Wing |
| The Seated Scribe | Unknown (Egyptian Old Kingdom) | c. 2620–2500 BC | Salle 635, Egyptian Antiquities |
| Bastet Cat Statue | Unknown (Egyptian Late Period) | c. 664–332 BC | Salle 630, Egyptian Antiquities |
| Air | Aristide Maillol | 1938 | Jardin des Tuileries |

Each sculpture has five structured knowledge sections: `key_facts`, `visual_description`, `historical_context`, `technique`, `story`.

---

## Quick Start — Local Development

### 1. Clone and set up environment

```bash
git clone <repo-url>
cd louvre-ar-backend

conda create -n contextar python=3.10
conda activate contextar
pip install -r requirements.txt
```

### 2. Set up API key

```bash
cp .env.example .env
# Edit .env and fill in your OPENAI_API_KEY
```

### 3. Start the server

The FAISS index is already committed — no rebuild needed.

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Server: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

---

## Testing Guide

The `/ask` endpoint supports three independent usage patterns. You can start from the simplest and add complexity as your integration matures. **None of them require a headset.**

---

### Level 1 — Pure QA (AI answer only)

Use this to verify the AI knowledge base and answer quality. No sensor data, no image, no mode selection. The server defaults to `FULL_VOICE` (full immersive answer).

```bash
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Venus de Milo"}'
```

```bash
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did the Dying Slave cause controversy?"}'
```

**Expected response:**
```json
{
  "mode": "FULL_VOICE",
  "answer": "The Dying Slave is a marble sculpture by Michelangelo...",
  "exhibit": ""
}
```

---

### Level 2 — Test specific response modes

Use this to test how the frontend should render different response lengths. Pass `mode` directly to bypass the context router entirely.

```bash
# One-sentence card (~20 words) — for crowded, quick-glance scenarios
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Winged Victory", "mode": "GLANCE_CARD"}'

# Short answer (~50 words) — for interested but brief engagement
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Winged Victory", "mode": "BRIEF_TEXT"}'

# Full immersive answer (~150 words) — for deeply engaged visitors
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Winged Victory", "mode": "FULL_VOICE"}'

# Brief answer + quiet-spot nudge — for engaged visitors in a crowd
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about the Winged Victory", "mode": "BRIEF_TEXT_PROMPT"}'
```

**All four valid modes:**

| Mode | Target length | When to use |
|---|---|---|
| `GLANCE_CARD` | ~20 words | Crowded room, visitor glancing briefly |
| `BRIEF_TEXT` | ~50 words | Low crowd, brief interest |
| `FULL_VOICE` | ~150 words | Low crowd, deeply engaged |
| `BRIEF_TEXT_PROMPT` | ~60 words | Engaged visitor but crowded — includes a nudge toward a quieter spot |

---

### Level 3 — Full context router

Use this to test the complete XR flow. Send sensor values the way your device would, and let the server decide the mode automatically.

```bash
# Visitor passing by — expect NO_RESPONSE, empty answer
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about this sculpture","state":{"crowd":"low","noise":"quiet","gaze_duration":2.0}}'

# Briefly interested, low crowd — expect BRIEF_TEXT
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about this sculpture","state":{"crowd":"low","noise":"quiet","gaze_duration":8.0}}'

# Glancing, crowded room — expect GLANCE_CARD
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about this sculpture","state":{"crowd":"crowded","noise":"noisy","gaze_duration":10.0}}'

# Deeply engaged, low crowd — expect FULL_VOICE
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about this sculpture","state":{"crowd":"low","noise":"quiet","gaze_duration":20.0}}'

# Deeply engaged, crowded — expect BRIEF_TEXT_PROMPT
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Tell me about this sculpture","state":{"crowd":"crowded","noise":"noisy","gaze_duration":20.0}}'
```

**Routing logic:**

```
gaze_duration < 5s                    →  NO_RESPONSE       (do not interrupt)
5s ≤ gaze_duration < 15s, crowded    →  GLANCE_CARD
5s ≤ gaze_duration < 15s, low crowd  →  BRIEF_TEXT
gaze_duration ≥ 15s, crowded         →  BRIEF_TEXT_PROMPT
gaze_duration ≥ 15s, low crowd       →  FULL_VOICE
```

Note: `noise` does not affect the mode — audio is delivered through earphones, so environment noise is irrelevant to routing.

---

### Level 4 — With sculpture recognition

Add `image_base64` to any of the above patterns. The server calls GPT-4o Vision to identify which sculpture is in the image, then tailors the answer accordingly.

```json
{
  "question": "Tell me about this sculpture",
  "image_base64": "<base64-encoded JPEG or PNG>",
  "state": { "crowd": "low", "noise": "quiet", "gaze_duration": 20.0 }
}
```

When recognition succeeds, `exhibit` in the response will contain the sculpture name, and the answer will be specific to that work.

**To convert an image to base64 for testing:**
```bash
# macOS / Linux
base64 -i my_photo.jpg | tr -d '\n'
```

```python
# Python
import base64
with open("my_photo.jpg", "rb") as f:
    print(base64.b64encode(f.read()).decode())
```

---

### Using Swagger UI instead of curl

Open `<BASE_URL>/docs` in any browser. Every field above is available as a form — no terminal needed. Useful for quick exploration on phone or tablet.

---

## Sculpture Recognition — How It Works

### The server requires the frontend to send a photo

The server has **no camera and no video stream**. Recognition only happens when the frontend explicitly includes `image_base64` in the request. The pipeline is:

```
Frontend captures one frame
    ↓  encodes as base64 JPEG
    ↓  includes in POST /ask body
Server calls GPT-4o Vision (~1–3 seconds)
    ↓
Returns { exhibit: "Venus de Milo", ... }
```

### This is not frame-by-frame — and that is intentional

GPT-4o Vision takes 1–3 seconds per call, which makes continuous streaming impractical. The recommended integration pattern for XR:

1. Unity continuously tracks `gaze_duration` on-device
2. When `gaze_duration` crosses the 5-second threshold, trigger **one** capture + API call
3. Cache the returned `exhibit` name for the rest of the interaction — no need to re-identify on every question

This pattern aligns perfectly with the context router: gaze under 5 seconds returns `NO_RESPONSE` anyway, so recognition only fires at the exact moment the visitor is worth addressing.

### If the image is unclear or not one of the eight sculptures

The recognizer returns `confidence: "low"` or `name: "unknown"`. In that case, the server falls back to answering the question from the general knowledge base without sculpture-specific context.

---

## API Reference

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /ask` — request fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `string` | Yes | Visitor's natural-language question |
| `image_base64` | `string` | No | Base64 JPEG/PNG; omit to skip recognition |
| `state` | `object` | No | Sensor state; omit to skip context routing |
| `state.crowd` | `"low"` \| `"crowded"` | No | Default: `"low"` |
| `state.noise` | `"quiet"` \| `"noisy"` | No | Default: `"quiet"` |
| `state.gaze_duration` | `float` (seconds) | No | Default: `0.0` |
| `mode` | `string` | No | Direct mode override — takes priority over `state` |

**Priority:** `mode` (if set) → `state` (if set) → default `FULL_VOICE`

### `POST /ask` — response fields

| Field | Notes |
|---|---|
| `mode` | The mode used: `NO_RESPONSE` \| `BRIEF_TEXT` \| `GLANCE_CARD` \| `FULL_VOICE` \| `BRIEF_TEXT_PROMPT` |
| `answer` | Text answer; empty string when `mode` is `NO_RESPONSE` |
| `exhibit` | Recognised sculpture name; empty string if not identified |

---

## Unity / Quest Integration

```csharp
private const string BASE_URL = "<ask a team member for the URL>";

IEnumerator AskServer(string question, float gazeDuration,
                      string crowd, string noise)
{
    var body = new AskRequest
    {
        question = question,
        state    = new AskState { crowd = crowd, noise = noise, gaze_duration = gazeDuration }
    };

    string json = JsonUtility.ToJson(body);
    using var req = new UnityWebRequest($"{BASE_URL}/ask", "POST");
    req.uploadHandler   = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
    req.downloadHandler = new DownloadHandlerBuffer();
    req.SetRequestHeader("Content-Type", "application/json");
    yield return req.SendWebRequest();

    if (req.result == UnityWebRequest.Result.Success)
        HandleResponse(JsonUtility.FromJson<AskResponse>(req.downloadHandler.text));
}

void HandleResponse(AskResponse resp)
{
    switch (resp.mode)
    {
        case "NO_RESPONSE":       break;                          // visitor passing by
        case "GLANCE_CARD":       ShowGlanceCard(resp.answer);   break;
        case "BRIEF_TEXT":        ShowBriefText(resp.answer);    break;
        case "FULL_VOICE":        ShowFullOverlay(resp.answer);  break;
        case "BRIEF_TEXT_PROMPT": ShowBriefText(resp.answer);    break;
    }
}
```

```csharp
[Serializable] public class AskState    { public string crowd; public string noise; public float gaze_duration; }
[Serializable] public class AskRequest  { public string question; public string image_base64; public AskState state; }
[Serializable] public class AskResponse { public string mode; public string answer; public string exhibit; }
```

---

## Deployment

Deployed on Railway via the included `Dockerfile`. Redeploys automatically on every push to `main`.

### Required environment variable

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`) |

### Rebuild FAISS index (only needed after editing `exhibits_data.py`)

```bash
python rag_engine.py --build
git add faiss_index/
git commit -m "Rebuild FAISS index"
git push origin main
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API server | FastAPI + Uvicorn |
| LLM | GPT-4o (QA + Vision) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector search | FAISS (via LangChain) |
| Image processing | OpenCV |
| Deployment | Railway (Docker) |
