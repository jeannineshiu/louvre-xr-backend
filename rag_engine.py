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
import re
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
    "Speak in a friendly, personal tone — as if you are standing right there with the visitor.\n\n"
    "Grounding: answer ONLY from the exhibit information below. If it does not "
    "contain the answer — the visitor asks about an artwork that is not one of "
    "these exhibits, about an artist's life or other works beyond what is written "
    "here, or about anything else the text doesn't cover — say plainly, in the "
    "visitor's language, that you don't have information about that, and offer to "
    "tell them about one of the exhibits you do know instead. NEVER fill the gap "
    "from general knowledge, even for famous artworks or artists you are certain "
    "about: retrieval sometimes hands you a nearby-but-wrong exhibit's text, and "
    "answering from memory instead of declining is the failure mode this rule "
    "exists to prevent.\n\n"
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


_HISTORY_AWARE_NOTE = (
    "You have access to the conversation history — use it to give "
    "contextually aware answers and avoid repeating information already given."
)


def _system_prompt(mode: str, context: str, history_aware: bool = False) -> str:
    """Build the system prompt for a mode from the shared persona + instructions.

    Static content (persona, mode instructions, history-aware note — all fixed
    per mode, independent of the retrieved chunks) comes first; the
    per-query retrieved context comes last. This keeps the prompt's leading
    portion identical across every query in the same mode, which is what
    lets provider-side prompt caching (OpenAI/Anthropic prefix caching) reuse
    it instead of recomputing from scratch on every request — a dynamic
    block anywhere before the tail would invalidate the cached prefix.
    """
    persona = _MODE_PERSONA.get(mode, _PERSONA_GUIDE)
    instructions = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS[_DEFAULT_MODE])
    static_parts = [persona, instructions]
    if history_aware:
        static_parts.append(_HISTORY_AWARE_NOTE)
    static = "\n\n".join(static_parts)
    return f"{static}\n\nExhibit information:\n{context}"


# FAISS distance below which a retrieved chunk counts as "possibly relevant".
# (Note: LangChain's FAISS wrapper uses IndexFlatL2, so these scores are
# SQUARED L2. Embeddings are unit-norm, so d = 2 - 2*cos — the distance axis
# is just an affine rescaling of cosine similarity; 1.0 here means cos 0.5.)
#
# This gate is a coarse cost filter, NOT the correctness gate. It exists to
# skip the GPT-4o call (and return _OUT_OF_SCOPE_ANSWER) for questions so far
# from the index that generating is pointless — "what's the weather", ticket
# refunds. It CANNOT be the correctness gate, for two measured reasons
# (2026-08-14, `python -m eval.calibrate_threshold --candidate 1.0`):
#
#   1. Near-miss off-topic questions (other Louvre works, our artists' other
#      works, name collisions like "Venus of Willendorf") score 0.66-1.48 —
#      squarely inside and above the on-topic range (0.35-0.93 English).
#      No threshold separates them, and _exact_match_ids() bypasses the
#      gate entirely for artist-name questions ("Who was Antonio Canova?").
#   2. Cross-lingual on-topic questions score far higher than their English
#      twins: the four Chinese golden probes landed 1.055-1.230, so the old
#      1.0 cutoff (calibrated on English-only probes) wrongly declined every
#      Chinese question despite the persona promising Chinese answers.
#
# Correctness therefore lives in the prompt's Grounding instruction
# (_PERSONA_GUIDE): the LLM sees the retrieved text and declines when it
# doesn't answer the question. This threshold is set loose — above the worst
# observed on-topic probe (zh 1.230) and at the floor of the far-off-topic
# band (1.288-1.767) — so its failure mode is "one wasted LLM call that
# politely declines", never "a real question hard-declined".
#
# Re-run `python -m eval.calibrate_threshold` after any change to
# build_index()'s chunking or to exhibits_data.py that meaningfully changes
# section content — don't hand-tune this without data. When adding a
# supported language to the persona, add probes in that language first.
_RELEVANCE_THRESHOLD = 1.35

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


def _exhibit_documents(exhibit: dict) -> list[Document]:
    """One Document per non-empty section of a single exhibit. Factored out
    of build_index() so the exact-match lookup below (_DOCS_BY_ID) can get
    the same chunks the FAISS index holds without needing a vectorstore or
    any embedding calls."""
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
    docs = []
    for field, label in _SECTION_FIELDS:
        value = exhibit.get(field, "")
        if not value:
            continue
        docs.append(Document(
            page_content=f"{header}\n\n{label}: {value}",
            metadata={**base_meta, "section": field},
        ))
    return docs


# Exhibit id → its section chunks / display name — pure Python, built once at
# import time. Lets the exact-match short-circuit in _retrieve() hand back
# full chunk content for a proper-noun hit without touching the vectorstore.
_DOCS_BY_ID: dict[str, list[Document]] = {e["id"]: _exhibit_documents(e) for e in EXHIBITS}
_EXHIBIT_NAMES: dict[str, str] = {e["id"]: e["name"] for e in EXHIBITS}


def _proper_noun_patterns() -> list[tuple[re.Pattern, str]]:
    """(\\b-bounded, case-insensitive pattern, exhibit id) pairs for every
    exhibit name and named (non-"Unknown ...") artist. Dense embedding
    similarity can under-rank a chunk whose relevance hinges on an exact
    proper noun rather than general semantic overlap — this corpus is only
    12 exhibits, so a cheap exact-match pass is a much better ROI here than
    standing up a full BM25/RRF hybrid-search pipeline. See _retrieve()."""
    patterns = []
    for exhibit in EXHIBITS:
        patterns.append((re.compile(r"\b" + re.escape(exhibit["name"].lower()) + r"\b"), exhibit["id"]))
        artist = exhibit.get("artist", "")
        if artist and not artist.lower().startswith("unknown"):
            patterns.append((re.compile(r"\b" + re.escape(artist.lower()) + r"\b"), exhibit["id"]))
    return patterns


_PROPER_NOUN_PATTERNS = _proper_noun_patterns()


def _exact_match_ids(query: str) -> list[str]:
    """Exhibit ids whose name or artist appears verbatim (whole-word,
    case-insensitive) in `query`, first-match order, deduped."""
    q = query.lower()
    ids: list[str] = []
    for pattern, eid in _PROPER_NOUN_PATTERNS:
        if eid not in ids and pattern.search(q):
            ids.append(eid)
    return ids


def build_index() -> FAISS:
    """Convert EXHIBITS list → one LangChain Document per exhibit section → FAISS index."""
    docs = [doc for exhibit in EXHIBITS for doc in _exhibit_documents(exhibit)]

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


def _group_by_exhibit(scored: list[tuple[Document, float]]) -> list[tuple[str, str, float, list[Document]]]:
    """Group scored chunks by exhibit, keeping the best (lowest) score per
    exhibit. Returns [(exhibit_id, exhibit_name, best_score, chunks)], best
    exhibit first."""
    groups: dict[str, dict] = {}
    for doc, score in scored:
        eid = doc.metadata["id"]
        group = groups.setdefault(eid, {"name": doc.metadata["name"], "best_score": score, "docs": []})
        group["docs"].append(doc)
        group["best_score"] = min(group["best_score"], score)
    ordered = sorted(groups.items(), key=lambda item: item[1]["best_score"])
    return [(eid, g["name"], g["best_score"], g["docs"]) for eid, g in ordered]


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
        """Retrieve chunks for `query`, keeping exhibits whose best chunk
        clears _RELEVANCE_THRESHOLD, plus any exhibit whose name/artist is
        mentioned verbatim in `query` even if dense search ranked it low or
        missed it — see _proper_noun_patterns(). Exact matches are ordered
        first (strongest relevance signal), then the rest of the dense
        passes in score order. Returns (chunks, exhibit names), both deduped
        by exhibit."""
        scored = self._vectorstore.similarity_search_with_score(query, k=_RETRIEVAL_K)
        groups = _group_by_exhibit(scored)
        dense_hits = {eid: (name, docs) for eid, name, score, docs in groups if score < _RELEVANCE_THRESHOLD}

        ordered_ids = [eid for eid in _exact_match_ids(query)]
        for eid in dense_hits:
            if eid not in ordered_ids:
                ordered_ids.append(eid)

        sources = []
        docs = []
        for eid in ordered_ids:
            name, exhibit_docs = dense_hits.get(eid, (_EXHIBIT_NAMES.get(eid), _DOCS_BY_ID.get(eid, [])))
            sources.append(name)
            docs.extend(exhibit_docs)
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
        system_content = _system_prompt(mode, context, history_aware=True)

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
