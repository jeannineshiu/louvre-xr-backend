"""
ContextAR - Relevance-threshold calibration probe.

rag_engine._RELEVANCE_THRESHOLD gates whether a question is "about one of our
exhibits" at all (see the comment above it). It was calibrated against the
OLD one-Document-per-exhibit index and has not been re-validated since
build_index() switched to per-section chunking (INDEX_SCHEMA_VERSION 2) —
the embedding distance distribution shifts with chunk granularity, so the
old 1.0 cutoff is unverified for the current index.

This script does NOT change the threshold. It probes the live FAISS index
with on-topic queries (from eval/golden_set.jsonl, reproducing exactly what
RAGEngine._retrieve() is actually called with in production — see
_load_on_topic_queries) and off-topic/adversarial queries, prints the
best-chunk L2 distance for each, and reports the gap between the on-topic
and off-topic distributions so a human can pick a defensible cutoff from
real numbers instead of hand-tuning it.

Costs money: each query is one OpenAI embedding call. Requires
OPENAI_API_KEY.

Usage:
    python -m eval.calibrate_threshold
    python -m eval.calibrate_threshold --candidate 0.85
"""

import argparse
import json
from pathlib import Path

from rag_engine import _RETRIEVAL_HISTORY_WINDOW, _group_by_exhibit, get_or_build_index

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"

# Adversarial off-topic queries — deliberately outside the 12-exhibit knowledge
# base. Extend this list whenever a real out-of-scope question slips through.
OFF_TOPIC_QUERIES = [
    "What is the capital of France?",
    "Tell me about the Mona Lisa.",
    "What time does the museum close?",
    "Can I get a refund on my ticket?",
    "Who painted the Sistine Chapel ceiling?",
    "What's the weather like in Paris today?",
    "How do I get a student discount?",
    "Tell me about the Eiffel Tower.",
]


def _load_on_topic_queries() -> list[tuple[str, str]]:
    """(id, retrieval_query) pairs from the golden set, mirroring exactly what
    RAGEngine._retrieve() would actually be called with in production:
      - skips expect_decline cases (those are supposed to score like off-topic)
      - skips NAVIGATION-mode cases (they bypass RAG/_retrieve() entirely —
        see qa_pipeline._navigation_answer — so their embedding distance is
        meaningless here)
      - for history cases, folds in the last _RETRIEVAL_HISTORY_WINDOW turns
        the same way _query_with_history does, since a bare pronoun-only
        follow-up embeds nowhere near the exhibit on its own by design
    """
    queries = []
    with open(GOLDEN_SET_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            if case.get("expect_decline") or case.get("mode") == "NAVIGATION":
                continue
            history = case.get("history")
            if history:
                recent = history[-_RETRIEVAL_HISTORY_WINDOW:]
                retrieval_query = " ".join(m["content"] for m in recent) + " " + case["question"]
            else:
                retrieval_query = case["question"]
            queries.append((case["id"], retrieval_query))
    return queries


def _best_distance(vectorstore, query: str) -> float:
    scored = vectorstore.similarity_search_with_score(query, k=8)
    groups = _group_by_exhibit(scored)
    return groups[0][1] if groups else float("inf")


def main():
    parser = argparse.ArgumentParser(description="Probe FAISS best-chunk distances for threshold calibration")
    parser.add_argument("--candidate", type=float, default=None,
                        help="report how many on/off-topic queries this threshold would classify correctly")
    args = parser.parse_args()

    vectorstore = get_or_build_index()

    print("\n-- On-topic (golden set) --")
    on_topic_scores = []
    for case_id, retrieval_query in _load_on_topic_queries():
        dist = _best_distance(vectorstore, retrieval_query)
        on_topic_scores.append(dist)
        print(f"  {dist:.3f}  {case_id}: {retrieval_query}")

    print("\n-- Off-topic (adversarial) --")
    off_topic_scores = []
    for question in OFF_TOPIC_QUERIES:
        dist = _best_distance(vectorstore, question)
        off_topic_scores.append(dist)
        print(f"  {dist:.3f}  {question}")

    on_max = max(on_topic_scores)
    off_min = min(off_topic_scores)
    print(f"\nOn-topic best-chunk distance:  min={min(on_topic_scores):.3f}  max={on_max:.3f}")
    print(f"Off-topic best-chunk distance: min={off_min:.3f}  max={max(off_topic_scores):.3f}")

    if on_max < off_min:
        print(f"\nClean separation — any threshold in ({on_max:.3f}, {off_min:.3f}) works. "
              f"Suggested: {(on_max + off_min) / 2:.3f}")
    else:
        print(
            "\nNo clean separation — on-topic and off-topic distance ranges overlap. "
            "_RELEVANCE_THRESHOLD cannot perfectly distinguish these queries; pick the "
            "value that minimizes the failure mode you care about more (false declines "
            "on real questions vs. hallucinated answers to off-topic ones) and add the "
            "misclassified queries above as new golden_set.jsonl cases."
        )

    if args.candidate is not None:
        on_fail = sum(1 for d in on_topic_scores if d >= args.candidate)
        off_fail = sum(1 for d in off_topic_scores if d < args.candidate)
        print(f"\nCandidate threshold {args.candidate}: "
              f"{on_fail}/{len(on_topic_scores)} on-topic would be wrongly declined, "
              f"{off_fail}/{len(off_topic_scores)} off-topic would be wrongly answered.")


if __name__ == "__main__":
    main()
