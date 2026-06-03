# Louvre XR Backend

FastAPI backend for an XR museum companion system.
Exhibition: **Louvre Museum & Jardin des Tuileries, Paris** — eight iconic sculptures from antiquity to the 20th century.

The backend receives a visitor's question and optional context (gaze duration, crowd density, ambient noise) from an XR device, optionally identifies the sculpture from a camera frame, and returns a mode decision with a length-appropriate text answer.

> **Access:** This server is deployed on Railway. Contact a team member for the public URL — it is not published here to limit access to the team.

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

| Sculpture | Artist | Date | Location in Louvre |
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

### 1. Clone and create environment

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

Server available at `http://localhost:8000`.
Interactive docs at `http://localhost:8000/docs`.

---

## API Reference

### `GET /health`

Health check.

```json
{ "status": "ok" }
```

---

### `POST /ask`

Main QA endpoint. Supports three usage patterns:

#### Pattern 1 — Simplest (no device needed)

No state, no mode. Defaults to `FULL_VOICE`.

```json
{
  "question": "Who created the Winged Victory and when?"
}
```

#### Pattern 2 — Direct mode (skip context routing)

Specify the response length directly. Useful for frontend testing without sensor data.

```json
{
  "question": "Who created the Winged Victory and when?",
  "mode": "GLANCE_CARD"
}
```

#### Pattern 3 — Full XR flow (context router active)

Send sensor state from the device. The server decides the mode automatically.

```json
{
  "question": "Who created the Winged Victory and when?",
  "state": {
    "crowd": "low",
    "noise": "quiet",
    "gaze_duration": 20.0
  }
}
```

#### With sculpture recognition (any pattern)

Add a base64-encoded camera frame. The server calls GPT-4o Vision to identify the sculpture and enriches the answer accordingly.

```json
{
  "question": "Tell me about this sculpture",
  "image_base64": "<base64 JPEG/PNG>",
  "state": { "crowd": "low", "noise": "quiet", "gaze_duration": 20.0 }
}
```

#### Request fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `string` | Yes | Visitor's natural-language question |
| `image_base64` | `string` | No | Base64 JPEG/PNG from camera; omit to skip recognition |
| `state` | `object` | No | Sensor state from device; omit to skip context routing |
| `state.crowd` | `"low"` \| `"crowded"` | No | Default: `"low"` |
| `state.noise` | `"quiet"` \| `"noisy"` | No | Default: `"quiet"` |
| `state.gaze_duration` | `float` (seconds) | No | Default: `0.0` |
| `mode` | `string` | No | Direct override; see mode table below |

#### Response

```json
{
  "mode": "FULL_VOICE",
  "answer": "The Winged Victory of Samothrace was created around 190 BC...",
  "exhibit": "Winged Victory of Samothrace"
}
```

| Field | Notes |
|---|---|
| `mode` | See mode table below |
| `answer` | Text answer; empty string for `NO_RESPONSE` |
| `exhibit` | Recognised sculpture name; empty string if not identified |

---

## Response Modes

| Mode | Trigger | Target length | Unity action |
|---|---|---|---|
| `NO_RESPONSE` | `gaze_duration < 5s` | — | Do nothing — visitor is passing by |
| `BRIEF_TEXT` | `5–15s`, low crowd | ~50 words | Short text panel |
| `GLANCE_CARD` | `5–15s`, crowded | ~20 words | Minimal one-line card |
| `FULL_VOICE` | `>15s`, low crowd | ~150 words | Full overlay + audio via Meta TTS |
| `BRIEF_TEXT_PROMPT` | `>15s`, crowded | ~60 words | Brief text + nudge toward quieter spot |

**Note:** `noise` does not affect the mode — audio is delivered through earphones.

---

## Context Routing Logic

```
gaze_duration < 5s                    →  NO_RESPONSE
5s ≤ gaze_duration < 15s, crowded    →  GLANCE_CARD
5s ≤ gaze_duration < 15s, low crowd  →  BRIEF_TEXT
gaze_duration ≥ 15s, crowded         →  BRIEF_TEXT_PROMPT
gaze_duration ≥ 15s, low crowd       →  FULL_VOICE
```

Thresholds are defined as constants in `context_router.py` and can be tuned without touching the logic.

---

## Testing Without a Headset

Once the server is running (locally or via the team URL), test from any browser or terminal.

### Swagger UI

Open `/docs` in a browser for an interactive interface — no code needed.

### curl examples

```bash
# Health check
curl <BASE_URL>/health

# Simplest call — defaults to FULL_VOICE
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about this sculpture"}'

# Specify mode directly
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Tell me about this sculpture", "mode": "GLANCE_CARD"}'

# Full XR flow with sensor state
curl -X POST <BASE_URL>/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tell me about this sculpture",
    "state": {"crowd": "low", "noise": "quiet", "gaze_duration": 20.0}
  }'
```

Replace `<BASE_URL>` with the URL provided by the team.

### Demo scenarios

| Scenario | `gaze_duration` | `crowd` | Expected mode |
|---|---|---|---|
| Passing by | `2.0` | `"low"` | `NO_RESPONSE` |
| Brief interest | `8.0` | `"low"` | `BRIEF_TEXT` |
| Quick glance, crowded | `10.0` | `"crowded"` | `GLANCE_CARD` |
| Deeply engaged | `20.0` | `"low"` | `FULL_VOICE` |
| Engaged, crowded | `20.0` | `"crowded"` | `BRIEF_TEXT_PROMPT` |

---

## Unity / Quest Integration

Quest 3 connects over Wi-Fi or directly to the Railway URL.

```csharp
private const string BASE_URL = "<ask a team member for the URL>";

IEnumerator AskServer(string question, float gazeDuration,
                      string crowd, string noise)
{
    var body = new AskRequest
    {
        question = question,
        state = new AskState
        {
            crowd         = crowd,
            noise         = noise,
            gaze_duration = gazeDuration
        }
    };

    string json = JsonUtility.ToJson(body);
    using var req = new UnityWebRequest($"{BASE_URL}/ask", "POST");
    req.uploadHandler   = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
    req.downloadHandler = new DownloadHandlerBuffer();
    req.SetRequestHeader("Content-Type", "application/json");

    yield return req.SendWebRequest();

    if (req.result == UnityWebRequest.Result.Success)
    {
        var resp = JsonUtility.FromJson<AskResponse>(req.downloadHandler.text);
        HandleResponse(resp);
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

The server is deployed on Railway using the included `Dockerfile`.

### Environment variable required

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`) |

Railway injects the `PORT` variable automatically — no configuration needed.

### Rebuild FAISS index (only if `exhibits_data.py` is updated)

```bash
python rag_engine.py --build
git add faiss_index/
git commit -m "Rebuild FAISS index"
git push origin main
```

Railway will redeploy automatically on push.

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
