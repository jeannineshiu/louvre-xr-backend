"""
ContextAR - RAG Engine
Builds a FAISS vector store from exhibits_data.py and answers
questions using LangChain + OpenAI embeddings + GPT-4o.

Each response mode gets a tailored prompt so the LLM targets the
correct length and tone from the start — not post-hoc truncation.

Usage:
    # First run: build and save the index
    python rag_engine.py --build

    # Query
    python rag_engine.py --query "Who created this sculpture and when?"
"""

import argparse
import hashlib
import logging
import os
import sys

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from cache import TTLCache
from exhibits_data import EXHIBITS

load_dotenv()

logger = logging.getLogger(__name__)

FAISS_INDEX_PATH = "faiss_index"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL  = "gpt-4o"

# Bump whenever build_index()'s document/chunking shape changes (fields
# used, section splitting, header format, ...) so a stale committed index
# built under the old shape gets flagged even though EXHIBITS itself didn't
# change. See _source_hash() / is_index_fresh().
INDEX_SCHEMA_VERSION = 2  # v2: per-section chunking (was one Document per exhibit)


# ---------------------------------------------------------------------------
# Persona + mode instructions — single source of truth.
#
# This used to be three near-duplicate copies of the same prose: one baked
# into each PROMPT_* PromptTemplate (non-history RetrievalQA path), one in
# _MODE_INSTRUCTIONS (history-aware path), plus the shared preamble
# duplicated a third time inline in _query_with_history. Any prompt tweak
# had to be applied in three places to stay in sync. Both query paths now
# build their system prompt from _system_prompt() below, sourced from just
# these two dicts.
# ---------------------------------------------------------------------------

_PERSONA_GUIDE = (
    "You are Sophie, a warm and knowledgeable museum guide for MuseXR. "
    "You guide visitors through the Louvre Museum, Jardin des Tuileries, Paris, "
    "and one additional public sculpture in Sydney, Australia. "
    "The exhibition features iconic sculptures from antiquity to the 20th century. "
    "Use only the exhibit information below. "
    "Speak in a friendly, personal tone — as if you are standing right there with the visitor.\n\n"
    "Language: detect the language of the visitor's question and respond in that same language. "
    "If the question is in French, respond in French. If in Chinese, respond in Chinese. "
    "Always match the visitor's language.\n\n"
    "Shop guidance: whenever the visitor asks about merchandise, souvenirs, replicas, or where to buy, "
    "always include the relevant product URL from the exhibit information in your first response.\n\n"
    "Formatting: plain text only. Do NOT use markdown — no bold (**text**), no italics (*text*), "
    "no markdown links [text](url). Write URLs as plain text, e.g. boutique.louvre.fr/en/product/123"
)

_PERSONA_SHOP = (
    "You are Sophie, a shopping assistant for the Louvre Museum boutique.\n\n"
    "Language: detect the language of the visitor's question and respond in that same language."
)

# Which persona each mode uses; anything not listed here uses the guide persona.
_MODE_PERSONA = {
    "SHOP": _PERSONA_SHOP,
}

# GLANCE_CARD — visitor is passing through a crowd, 5–15 s gaze
#   Target: 1 punchy sentence, max ~20 words.
# BRIEF_TEXT — visitor is interested, 5–15 s gaze, low crowd
#   Target: 2–3 sentences, ~50 words.
# FULL_VOICE — visitor is deeply engaged, >15 s gaze, low crowd
#   Target: full immersive guide, maximum 100 words, with historical context and story.
# BRIEF_TEXT_PROMPT — visitor engaged >15 s but environment is crowded
#   Target: brief answer (~50 words) + a natural nudge toward a quieter spot.
# SHOP — visitor is asking about merchandise, souvenirs, replicas, or where to buy
#   Target: product info + URL only, no art history, max ~3 sentences.
#
# NOTE: there is no NAVIGATION entry here on purpose. Walking directions are
# answered from navigation_routes.py's deterministic (from_id, to_id) lookup
# table (see qa_pipeline._navigation_answer), not from this RAG index — the
# exhibit documents below don't contain room/wing data, so routing this mode
# through the LLM produced confident, plausible-sounding, and WRONG room
# numbers. See eval/golden_set.jsonl "navigation_grounding" for the regression
# test that caught this.
_MODE_INSTRUCTIONS = {
    "GLANCE_CARD": (
        "Answer in exactly ONE sentence (maximum 20 words). "
        "State only the single most surprising or memorable fact."
    ),
    "BRIEF_TEXT": (
        "Answer in 2–3 sentences (around 50 words). "
        "Give the key fact and one interesting detail. Be clear and engaging."
    ),
    "FULL_VOICE": (
        "Answer in 3–4 sentences (maximum 100 words). "
        "Include: the direct answer to the question, one relevant historical detail or "
        "story, and a closing thought that invites the visitor to look more closely at "
        "the sculpture. Be warm and immersive, but concise."
    ),
    "BRIEF_TEXT_PROMPT": (
        "Answer in 2–3 sentences (around 50 words). "
        "At the end, add one friendly sentence suggesting the visitor find a quieter spot "
        "for a more complete audio guide experience."
    ),
    "SHOP": (
        "Answer ONLY with merchandise information: available products, prices, sizes, and the "
        "shop URL. First mention the available products and prices, then end with the shop URL "
        "from the exhibit information. Always include the shop URL — it must appear in your "
        "answer. Do NOT add art history, navigation directions, or any other content. "
        "Plain text only — no markdown formatting. Maximum 3 sentences."
    ),
}

_DEFAULT_MODE = "BRIEF_TEXT"


def _system_prompt(mode: str, context: str) -> str:
    """Build the system prompt for a mode from the shared persona + instructions."""
    persona = _MODE_PERSONA.get(mode, _PERSONA_GUIDE)
    instructions = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS[_DEFAULT_MODE])
    return f"{persona}\n\nExhibit information:\n{context}\n\n{instructions}"


# FAISS L2 distance below which a retrieved chunk counts as "actually relevant".
# Also used as the out-of-scope gate: if no exhibit clears this bar, the question
# isn't about any of our 12 exhibits and we should decline rather than let the
# LLM answer from general world knowledge (see eval/golden_set.jsonl
# "out_of_scope_capital" / "out_of_scope_unknown_exhibit" — both hallucinated
# grounded-sounding answers before this gate was added).
#
# RE-CALIBRATED for section-chunk granularity (2026-07-20, via
# `python -m eval.calibrate_threshold` against the live per-section index):
#   on-topic best-chunk distances:  0.349–0.925 (18 golden-set cases,
#     NAVIGATION-mode and expect_decline cases excluded — they don't go
#     through this gate; history cases probed with history folded in, same
#     as _query_with_history)
#   off-topic best-chunk distances: 1.018 (Sistine Chapel) – 1.767 (unrelated)
# Clean separation with a gap of (0.925, 1.018) — 1.0 sits inside it and
# correctly classified all 18 on-topic / 8 off-topic probes (0 false
# declines, 0 false answers). Re-run `python -m eval.calibrate_threshold`
# after any change to build_index()'s chunking or to exhibits_data.py that
# meaningfully changes section content — don't hand-tune this without data.
_RELEVANCE_THRESHOLD = 1.0

_OUT_OF_SCOPE_ANSWER = (
    "I'm not able to help with that — I only know about the sculptures in this "
    "collection: " + ", ".join(e["name"] for e in EXHIBITS) + ". "
    "Ask me about one of those, or point your camera at a sculpture."
)

# How many recent history messages get folded into the *retrieval* query (not
# the final LLM prompt, which still sees the full history). Needed because a
# bare follow-up like "what else can you tell me about it?" embeds nowhere
# near the exhibit it refers to — see eval/golden_set.jsonl
# "history_followup_no_repeat".
_RETRIEVAL_HISTORY_WINDOW = 4

# Exhibits are chunked at section granularity (~6 chunks each — see
# build_index), not one chunk per exhibit, so a single nearest-neighbour
# isn't enough to gather every section of the exhibit actually being asked
# about. k=8 comfortably covers all sections of the top 1-2 matching
# exhibits without pulling in unrelated ones.
_RETRIEVAL_K = 8


# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

# Exhibit dict field → (chunk label, section key stored in chunk metadata).
# One Document per non-empty section, instead of one Document per exhibit —
# real chunk-level retrieval instead of a 12-row table lookup gated by which
# whole-exhibit blob happens to be closest.
_SECTION_FIELDS = [
    ("key_facts",          "Key facts"),
    ("visual_description", "What you see"),
    ("historical_context", "Historical context"),
    ("technique",          "Technique"),
    ("story",              "Story"),
    ("content",            "Summary"),
    ("shop",               "Shop & merchandise"),
]


_SOURCE_HASH_FILENAME = "source_hash.txt"


def _source_hash() -> str:
    """Hash of everything that determines index contents: exhibit data plus
    the chunking schema version. Lets CI detect a stale committed
    faiss_index/ (see is_index_fresh / --check-fresh) with zero OpenAI
    calls — pure Python source, no embeddings required."""
    payload = f"{INDEX_SCHEMA_VERSION}:{EXHIBITS!r}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_index_fresh() -> bool:
    """True if faiss_index/'s recorded source hash matches the current
    exhibits_data.py + chunking schema. False (including a missing hash
    file, e.g. an index built before this check existed) means someone
    needs to run `python rag_engine.py --build` and commit the result."""
    hash_path = os.path.join(FAISS_INDEX_PATH, _SOURCE_HASH_FILENAME)
    if not os.path.exists(hash_path):
        return False
    with open(hash_path) as f:
        return f.read().strip() == _source_hash()


def build_index() -> FAISS:
    """Convert EXHIBITS list → one LangChain Document per exhibit section → FAISS index."""
    docs = []
    for exhibit in EXHIBITS:
        base_meta = {
            "id":       exhibit["id"],
            "name":     exhibit["name"],
            "artist":   exhibit.get("artist", "Unknown"),
            "year":     exhibit.get("year", "Unknown"),
            "period":   exhibit["period"],
            "location": exhibit.get("location", "Unknown"),
        }
        header = (
            f"Name: {exhibit['name']}\n"
            f"Artist: {exhibit.get('artist', 'Unknown')}\n"
            f"Year: {exhibit.get('year', 'Unknown')}\n"
            f"Period: {exhibit['period']}\n"
            f"Location: {exhibit.get('location', 'Unknown')}"
        )
        for field, label in _SECTION_FIELDS:
            value = exhibit.get(field, "")
            if not value:
                continue
            docs.append(Document(
                page_content=f"{header}\n\n{label}: {value}",
                metadata={**base_meta, "section": field},
            ))

    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    vectorstore = FAISS.from_documents(docs, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    with open(os.path.join(FAISS_INDEX_PATH, _SOURCE_HASH_FILENAME), "w") as f:
        f.write(_source_hash())
    logger.info("index_built", extra={
        "chunk_count":    len(docs),
        "exhibit_count":  len(EXHIBITS),
        "path":           FAISS_INDEX_PATH,
    })
    return vectorstore


def load_index() -> FAISS:
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
    vectorstore = FAISS.load_local(
        FAISS_INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    logger.info("index_loaded", extra={"path": FAISS_INDEX_PATH})
    return vectorstore


def get_or_build_index() -> FAISS:
    if os.path.exists(FAISS_INDEX_PATH):
        return load_index()
    return build_index()


def _group_by_exhibit(scored: list[tuple[Document, float]]) -> list[tuple[str, float, list[Document]]]:
    """Group scored chunks by exhibit, keeping the best (lowest) score per
    exhibit. Returns [(exhibit_name, best_score, chunks)], best exhibit first."""
    groups: dict[str, dict] = {}
    for doc, score in scored:
        eid = doc.metadata["id"]
        group = groups.setdefault(eid, {"name": doc.metadata["name"], "best_score": score, "docs": []})
        group["docs"].append(doc)
        group["best_score"] = min(group["best_score"], score)
    ordered = sorted(groups.values(), key=lambda g: g["best_score"])
    return [(g["name"], g["best_score"], g["docs"]) for g in ordered]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RAGEngine:
    """
    Singleton-style wrapper. Load once, query many times.

    Example:
        rag = RAGEngine()
        result = rag.query("What is the technique used here?", mode="FULL_VOICE")
        print(result["answer"])
        print(result["sources"])
    """

    def __init__(self):
        self._vectorstore = get_or_build_index()
        self._llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.3)
        # (question, mode, max_length) → {"answer", "sources"}. Exhibit
        # content only changes via a redeploy (see rag_engine --build), so a
        # 10-minute TTL is purely about bounding staleness after a content
        # edit, not correctness.
        self._answer_cache = TTLCache(ttl_seconds=600, maxsize=512)

    def _retrieve(self, query: str) -> tuple[list[Document], list[str]]:
        """Retrieve chunks for `query`, keeping only exhibits whose best chunk
        clears _RELEVANCE_THRESHOLD. Returns (chunks, exhibit names) — chunks
        span every matched exhibit's retrieved sections, exhibit names deduped
        and ordered by relevance."""
        scored = self._vectorstore.similarity_search_with_score(query, k=_RETRIEVAL_K)
        groups = _group_by_exhibit(scored)
        passing = [g for g in groups if g[1] < _RELEVANCE_THRESHOLD]
        sources = [name for name, _, _ in passing]
        docs = [doc for _, _, docs in passing for doc in docs]
        return docs, sources

    def query(self, question: str, mode: str = "BRIEF_TEXT",
              max_length: int = None, history: list[dict] | None = None) -> dict:
        """
        Answer a visitor question using the knowledge base.

        Args:
            question:   natural language question
            mode:       response mode — selects the appropriate prompt.
                        One of: GLANCE_CARD | BRIEF_TEXT | FULL_VOICE | BRIEF_TEXT_PROMPT
            max_length: optional hard character cap
            history:    optional prior turns [{role: "user"|"assistant", content: str}, ...]

        Returns:
            {
                "answer":  str,
                "sources": list[str]   # exhibit names retrieved
            }
        """
        if history:
            return self._query_with_history(question, mode, max_length, history)

        # Different visitors frequently ask the same thing about a popular
        # exhibit ("Who made this?", "Tell me about this sculpture") — cache
        # the no-history path (the common case) to skip a repeat GPT-4o call.
        # History-aware queries aren't cached: the key space is effectively
        # unbounded (full conversation) and reuse across visitors is ~zero.
        cache_key = (question.strip().lower(), mode, max_length)
        return self._answer_cache.get_or_set(
            cache_key, lambda: self._answer(question, mode, max_length)
        )

    def _answer(self, question: str, mode: str, max_length: int | None) -> dict:
        docs, sources = self._retrieve(question)
        if not sources:
            logger.info("rag_out_of_scope", extra={"mode": mode})
            return {"answer": _OUT_OF_SCOPE_ANSWER, "sources": []}

        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        system_content = _system_prompt(mode, context)
        response = self._llm.invoke([
            SystemMessage(content=system_content),
            HumanMessage(content=question),
        ])
        answer = response.content.strip()

        if max_length and len(answer) > max_length:
            answer = answer[:max_length].rsplit(" ", 1)[0] + "…"

        return {"answer": answer, "sources": sources}

    def _query_with_history(self, question: str, mode: str,
                            max_length: int | None, history: list[dict]) -> dict:
        """History-aware query: retrieves docs, then calls GPT-4o with full conversation context."""
        # Fold in the last few history messages so a pronoun-only follow-up
        # ("what else can you tell me about it?") still embeds close to the
        # exhibit being discussed, instead of searching on "it" alone.
        recent = history[-_RETRIEVAL_HISTORY_WINDOW:]
        retrieval_query = " ".join(m["content"] for m in recent) + " " + question

        docs, sources = self._retrieve(retrieval_query)
        if not sources:
            logger.info("rag_out_of_scope", extra={"mode": mode, "with_history": True})
            return {"answer": _OUT_OF_SCOPE_ANSWER, "sources": []}

        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        system_content = _system_prompt(mode, context) + (
            "\n\nYou have access to the conversation history — use it to give "
            "contextually aware answers and avoid repeating information already given."
        )

        messages = [SystemMessage(content=system_content)]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=question))

        response = self._llm.invoke(messages)
        answer = response.content.strip()

        if max_length and len(answer) > max_length:
            answer = answer[:max_length].rsplit(" ", 1)[0] + "…"

        return {"answer": answer, "sources": sources}

    def find_similar(self, exhibit_name: str, k: int = 2) -> list[str]:
        docs = self._vectorstore.similarity_search(exhibit_name, k=_RETRIEVAL_K)
        seen: list[str] = []
        for doc in docs:
            name = doc.metadata["name"]
            if name not in seen:
                seen.append(name)
            if len(seen) >= k:
                break
        return seen


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ContextAR RAG Engine")
    parser.add_argument("--build", action="store_true", help="Rebuild the FAISS index")
    parser.add_argument("--check-fresh", action="store_true",
                        help="Exit 1 if faiss_index/ is stale relative to exhibits_data.py "
                             "(no OpenAI calls — for CI)")
    parser.add_argument("--query", type=str, help="Ask a question")
    parser.add_argument("--mode",  type=str, default="BRIEF_TEXT",
                        choices=list(_MODE_INSTRUCTIONS.keys()),
                        help="Response mode (default: BRIEF_TEXT)")
    args = parser.parse_args()

    if args.check_fresh:
        if is_index_fresh():
            print(f"{FAISS_INDEX_PATH}/ is up to date with exhibits_data.py")
        else:
            print(
                f"{FAISS_INDEX_PATH}/ is STALE relative to exhibits_data.py "
                "(or was built before schema tracking existed).\n"
                "Run `python rag_engine.py --build` and commit the updated "
                f"{FAISS_INDEX_PATH}/ directory."
            )
            sys.exit(1)

    if args.build:
        build_index()

    if args.query:
        rag = RAGEngine()
        result = rag.query(args.query, mode=args.mode)
        print(f"\n[{args.mode}] Answer: {result['answer']}")
        print(f"Sources: {', '.join(result['sources'])}")

    if not args.build and not args.query and not args.check_fresh:
        rag = RAGEngine()
        print("ContextAR RAG — type a question, Ctrl+C to quit\n")
        while True:
            try:
                q = input("Question: ").strip()
                if not q:
                    continue
                for m in _MODE_INSTRUCTIONS:
                    r = rag.query(q, mode=m)
                    print(f"\n  [{m}]\n  {r['answer']}")
                print()
            except KeyboardInterrupt:
                break
