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

Queries are probed in four groups, because lumping them together hides
what actually sets the cutoff:

  on-topic / single-turn   the question embeds on its own
  on-topic / multi-turn    _query_with_history has folded prior turns into
                           the query, which makes it longer and more diluted,
                           so its distances sit systematically higher
  off-topic / near-miss    Louvre-adjacent or artist-adjacent questions that
                           are NOT in the 12-exhibit knowledge base — these
                           are what the threshold has to actually catch
  off-topic / far          plainly unrelated questions; they score so far
                           away that they never bind the decision

The number that matters is the gap between the on-topic max and the
near-miss min, not the headline min/max over everything.

Costs money: each query is one OpenAI embedding call. Requires
OPENAI_API_KEY.

Usage:
    python -m eval.calibrate_threshold
    python -m eval.calibrate_threshold --candidate 0.85
"""

import argparse
import json
from pathlib import Path

from rag_engine import (
    _RETRIEVAL_HISTORY_WINDOW,
    _exact_match_ids,
    _group_by_exhibit,
    get_or_build_index,
)

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"

# Near-miss off-topic queries — the hard half of the problem. Every one of
# these is museum/art/artist-adjacent and shares vocabulary with the indexed
# sections, but none is answerable from the 12-exhibit knowledge base. They
# are the queries that land closest to the on-topic distribution, so they, not
# the far off-topic ones below, are what any candidate threshold has to clear.
#
# Categories deliberately covered:
#   - other famous Louvre works (Mona Lisa, Hammurabi, Raft of the Medusa, ...)
#   - sibling works by an artist we DO index (Michelangelo, Canova, Maillol)
#   - name collisions with an indexed exhibit (other Venuses, other Nikes)
#   - same-culture neighbours of an indexed exhibit (other Egyptian pieces)
NEAR_MISS_QUERIES = [
    # Other famous Louvre holdings, not in the knowledge base
    "Tell me about the Mona Lisa.",
    "Tell me about the Code of Hammurabi.",
    "What is Liberty Leading the People?",
    "Tell me about the Raft of the Medusa.",
    "What is the Great Sphinx of Tanis?",
    "Tell me about the Diana of Versailles.",
    # Sibling works / biography of artists we DO index.
    # NOTE: pick these carefully — the exhibit contexts are rich enough to
    # legitimately answer some artist-adjacent questions. "Who painted the
    # Sistine Chapel ceiling?" and "What other slaves did Michelangelo carve?"
    # were removed from this list because The Dying Slave's context actually
    # answers both (it names the Sistine ceiling diversion and The Rebellious
    # Slave) — they are on-topic, not near-misses. Grep exhibits_data.py
    # before adding a query here.
    "Tell me about Michelangelo's David.",
    "Tell me about Michelangelo's Pieta in Saint Peter's Basilica.",
    "Who was Antonio Canova?",
    "Tell me about Maillol's The Mediterranean.",
    # Name collisions with an indexed exhibit
    "What is the Venus of Willendorf?",
    "Tell me about the Nike of Paionios.",
    "What is the Venus of Arles?",
    # Same-culture neighbours of an indexed exhibit
    "Who was the Egyptian goddess Sekhmet?",
    "Tell me about the statue of Ramesses II.",
    "What is the Rosetta Stone?",
    # Classical sculpture adjacent to the Borghese Gladiator
    "Tell me about the Laocoon group.",
    "What is the Apollo Belvedere?",
]

# Far off-topic queries — plainly outside the domain (general knowledge and
# visitor-logistics questions). Kept because they are real things users type,
# but they sit so far from the index that they never bind the threshold; do
# not read a comfortable-looking gap off these. Extend whenever a real
# out-of-scope question slips through.
FAR_OFF_TOPIC_QUERIES = [
    "What is the capital of France?",
    "What time does the museum close?",
    "Can I get a refund on my ticket?",
    "What's the weather like in Paris today?",
    "How do I get a student discount?",
    "Tell me about the Eiffel Tower.",
    # Cross-lingual far-off-topic — see MULTILINGUAL_ON_TOPIC_QUERIES below.
    "法國的首都是哪裡？",
    "Quelle heure ferme le musée ?",
]

# Extra cross-lingual on-topic probes, on top of the golden-set cases already
# tagged with a non-"en" "lang" field (those are loaded automatically by
# _load_on_topic_queries and land in the same group — don't duplicate them
# here). The persona explicitly answers in the visitor's language (French and
# Chinese are called out in _PERSONA_GUIDE), but the chunks are English and
# text-embedding-3-small's cross-lingual alignment is weaker than its
# monolingual one — so these queries sit systematically further from the index
# than their English twins, and a threshold calibrated on English-only probes
# silently mis-declines them. Each entry mirrors an English golden-set
# question so the two distances are directly comparable.
EXTRA_MULTILINGUAL_QUERIES = [
    ("zh_winged_victory_basic", "薩莫色雷斯的勝利女神有多古老？是什麼時候被發現的？"),
    ("zh_bastet_symbolism",     "這座貓女神雕像代表什麼意義？"),
    ("zh_dying_slave_tomb",     "垂死的奴隸這座雕像最初是為了什麼而做的？"),
    ("fr_venus_creator",        "Qui a créé la Vénus de Milo et quand ?"),
    ("fr_winged_victory_full",  "Raconte-moi l'histoire de la Victoire de Samothrace."),
]


def _load_on_topic_queries() -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """(single_turn, multi_turn, multilingual) lists of (id, retrieval_query)
    pairs from the golden set, mirroring exactly what RAGEngine._retrieve()
    would actually be called with in production:
      - skips expect_decline AND expect_grounded_refusal cases. Both are
        deliberately out of scope, so counting them as on-topic would corrupt
        the very distribution this script measures. They differ only in which
        layer is expected to refuse: expect_decline means the coarse distance
        gate should fire (sources == []), expect_grounded_refusal means the
        query scores close enough that retrieval returns something and the
        prompt's grounding rule has to do the refusing. The latter are
        probed as off-topic via NEAR_MISS_QUERIES above.
      - skips NAVIGATION-mode cases (they bypass RAG/_retrieve() entirely —
        see qa_pipeline._navigation_answer — so their embedding distance is
        meaningless here)
      - routes cases tagged with a non-"en" "lang" into the multilingual
        group (joined by EXTRA_MULTILINGUAL_QUERIES), since cross-lingual
        queries embed systematically further from the English chunks
      - for history cases, folds in the last _RETRIEVAL_HISTORY_WINDOW turns
        the same way _query_with_history does, since a bare pronoun-only
        follow-up embeds nowhere near the exhibit on its own by design

    The two are returned separately because they are different distributions:
    a folded multi-turn query carries two or three turns of unrelated wording
    into the embedding, which pushes its best-chunk distance up regardless of
    how on-topic the underlying question is. Averaging them into one "on-topic"
    range inflates the apparent max and makes the threshold look tighter
    against off-topic queries than it is for either group on its own.
    """
    single_turn, multi_turn = [], []
    multilingual = list(EXTRA_MULTILINGUAL_QUERIES)
    with open(GOLDEN_SET_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            if (case.get("expect_decline")
                    or case.get("expect_grounded_refusal")
                    or case.get("mode") == "NAVIGATION"):
                continue
            history = case.get("history")
            if history:
                recent = history[-_RETRIEVAL_HISTORY_WINDOW:]
                retrieval_query = " ".join(m["content"] for m in recent) + " " + case["question"]
                multi_turn.append((case["id"], retrieval_query))
            elif case.get("lang", "en") != "en":
                multilingual.append((case["id"], case["question"]))
            else:
                single_turn.append((case["id"], case["question"]))
    return single_turn, multi_turn, multilingual


def _best_distance(vectorstore, query: str) -> float:
    scored = vectorstore.similarity_search_with_score(query, k=8)
    groups = _group_by_exhibit(scored)
    return groups[0][2] if groups else float("inf")


def _probe_group(vectorstore, title: str, labelled_queries: list[tuple[str, str]]) -> list[tuple[float, str]]:
    """Print and return [(distance, label)] for one query group.

    Queries whose text verbatim-matches an exhibit name or artist are flagged
    [exact-match -> ids]: production _retrieve() injects those exhibits'
    chunks regardless of distance, so for them the distance printed here does
    NOT decide whether the question gets answered — no threshold value can
    decline them. Only the grounding instruction in the prompt can.
    """
    print(f"\n-- {title} (n={len(labelled_queries)}) --")
    scored = []
    for label, retrieval_query in labelled_queries:
        dist = _best_distance(vectorstore, retrieval_query)
        scored.append((dist, label))
        suffix = "" if label == retrieval_query else f": {retrieval_query}"
        bypass = _exact_match_ids(retrieval_query)
        bypass_note = f"  [exact-match -> {', '.join(bypass)}]" if bypass else ""
        print(f"  {dist:.3f}  {label}{suffix}{bypass_note}")
    return scored


def _summarize(title: str, scored: list[tuple[float, str]]) -> None:
    if not scored:
        print(f"  {title:<24} (empty)")
        return
    lo, hi = min(scored), max(scored)
    caveat = "   <- n<3, range is not a bound" if len(scored) < 3 else ""
    print(f"  {title:<24} n={len(scored):<3} min={lo[0]:.3f} ({lo[1]})  max={hi[0]:.3f} ({hi[1]}){caveat}")


def main():
    parser = argparse.ArgumentParser(description="Probe FAISS best-chunk distances for threshold calibration")
    parser.add_argument("--candidate", type=float, default=None,
                        help="report how many on/off-topic queries this threshold would classify correctly")
    args = parser.parse_args()

    vectorstore = get_or_build_index()

    single_turn, multi_turn, multilingual = _load_on_topic_queries()
    single_scores = _probe_group(vectorstore, "On-topic / single-turn", single_turn)
    multi_scores = _probe_group(vectorstore, "On-topic / multi-turn (history folded in)", multi_turn)
    multilingual_scores = _probe_group(vectorstore, "On-topic / multilingual (zh/fr)", multilingual)
    near_scores = _probe_group(vectorstore, "Off-topic / near-miss",
                               [(q, q) for q in NEAR_MISS_QUERIES])
    far_scores = _probe_group(vectorstore, "Off-topic / far",
                              [(q, q) for q in FAR_OFF_TOPIC_QUERIES])

    on_scores = single_scores + multi_scores + multilingual_scores
    off_scores = near_scores + far_scores

    print("\n-- Per-group distance ranges --")
    _summarize("on-topic single-turn", single_scores)
    _summarize("on-topic multi-turn", multi_scores)
    _summarize("on-topic multilingual", multilingual_scores)
    _summarize("off-topic near-miss", near_scores)
    _summarize("off-topic far", far_scores)

    on_max, on_max_label = max(on_scores)
    # tag by group membership, not by comparing distances — two groups can tie
    off_tagged = ([(dist, label, "near-miss") for dist, label in near_scores]
                  + [(dist, label, "far") for dist, label in far_scores])
    off_min, off_min_label, binding_group = min(off_tagged)

    print(
        f"\nDecision boundary is set by these two queries:\n"
        f"  furthest on-topic  {on_max:.3f}  {on_max_label}\n"
        f"  closest off-topic  {off_min:.3f}  {off_min_label}  [{binding_group}]"
    )

    if on_max < off_min:
        gap = off_min - on_max
        print(
            f"\nSeparated on this sample — any threshold in ({on_max:.3f}, {off_min:.3f}) "
            f"classifies all {len(on_scores)} on-topic and {len(off_scores)} off-topic "
            f"queries correctly. Midpoint: {(on_max + off_min) / 2:.3f}\n"
            f"Gap width: {gap:.3f}. Treat a gap under ~0.10 as noise, not headroom — it "
            f"rests on one query on each side and will move the next time the index is "
            f"rebuilt or a phrasing changes. If the gap is that narrow, prefer the "
            f"conservative end (nearer the on-topic max) over the midpoint, so a new "
            f"near-miss query has to travel further before it gets answered."
        )
    else:
        overlap = [(dist, label) for dist, label in on_scores if dist >= off_min]
        print(
            f"\nNo clean separation — the on-topic and off-topic ranges overlap by "
            f"{on_max - off_min:.3f}. _RELEVANCE_THRESHOLD cannot perfectly separate "
            f"these queries; pick the value that minimizes the failure mode you care "
            f"about more (false declines on real questions vs. hallucinated answers to "
            f"off-topic ones), and add the misclassified queries above as new "
            f"golden_set.jsonl cases.\n"
            f"On-topic queries inside the off-topic range:"
        )
        for dist, label in sorted(overlap):
            print(f"  {dist:.3f}  {label}")

    if args.candidate is not None:
        print(f"\nCandidate threshold {args.candidate}:")
        for title, scores, wrong in (
            ("on-topic single-turn", single_scores, lambda d: d >= args.candidate),
            ("on-topic multi-turn", multi_scores, lambda d: d >= args.candidate),
            ("on-topic multilingual", multilingual_scores, lambda d: d >= args.candidate),
            ("off-topic near-miss", near_scores, lambda d: d < args.candidate),
            ("off-topic far", far_scores, lambda d: d < args.candidate),
        ):
            bad = [label for dist, label in scores if wrong(dist)]
            verb = "wrongly declined" if title.startswith("on-topic") else "wrongly answered"
            print(f"  {title:<24} {len(bad)}/{len(scores)} {verb}"
                  + (f"  -> {', '.join(bad)}" if bad else ""))


if __name__ == "__main__":
    main()
