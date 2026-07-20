"""
ContextAR - RAG Eval Harness

Runs the golden Q&A set in eval/golden_set.jsonl against the live RAGEngine
and reports:
  1. Deterministic checks — retrieval hit, length budget, markdown-free
     output, shop URL presence, required/forbidden substrings.
  2. An optional LLM-judge score (gpt-4o-mini) for groundedness (did the
     answer only use facts present in the retrieved context?) and relevance.

This makes real OpenAI API calls (RAGEngine query + optional judge) and
costs money on every run. Requires OPENAI_API_KEY.

Usage:
    python -m eval.run_eval                    # full run: deterministic + judge
    python -m eval.run_eval --no-judge          # deterministic checks only (cheap/fast)
    python -m eval.run_eval --case venus_de_milo_creator
    python -m eval.run_eval --fail-under 0.8    # exit 1 if pass rate < 80% (for CI)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from qa_pipeline import run as qa_run
from rag_engine import _RETRIEVAL_HISTORY_WINDOW, RAGEngine

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
JUDGE_MODEL = "gpt-4o-mini"


def load_cases(path: Path = GOLDEN_SET_PATH) -> list[dict]:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------

_MARKDOWN_PATTERNS = [
    re.compile(r"\*\*[^*]+\*\*"),                  # **bold**
    re.compile(r"(?<!\*)\*[^*\s][^*]*\*(?!\*)"),    # *italic*
    re.compile(r"\[[^\]]+\]\([^)]+\)"),             # [text](url)
]


def has_markdown(text: str) -> bool:
    return any(p.search(text) for p in _MARKDOWN_PATTERNS)


def deterministic_checks(case: dict, result: dict) -> dict:
    answer = result["answer"]
    sources = result["sources"]
    checks = {}

    if case.get("expected_exhibit"):
        checks["retrieval_hit"] = case["expected_exhibit"] in sources

    if case.get("expect_decline"):
        # Wording-independent: the out-of-scope guardrail (rag_engine._OUT_OF_SCOPE_ANSWER)
        # always returns sources=[] when it fires, regardless of the exact decline phrasing.
        checks["declined"] = sources == []

    if case.get("max_words"):
        checks["length_ok"] = len(answer.split()) <= case["max_words"]

    if case.get("check_no_markdown"):
        checks["no_markdown"] = not has_markdown(answer)

    if case.get("check_shop_url"):
        checks["shop_url_present"] = "boutique.louvre.fr" in answer

    must_include_any = case.get("must_include_any") or []
    if must_include_any:
        low = answer.lower()
        checks["must_include_any"] = any(s.lower() in low for s in must_include_any)

    must_not_include = case.get("must_not_include") or []
    if must_not_include:
        low = answer.lower()
        checks["must_not_include"] = not any(s.lower() in low for s in must_not_include)

    return checks


# ---------------------------------------------------------------------------
# LLM judge (groundedness / relevance)
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a strict evaluator for a museum RAG chatbot named Sophie. "
    "You will be given the retrieved exhibit context (the ONLY information Sophie is "
    "allowed to use), the visitor's question, and Sophie's answer. Judge two things:\n"
    "1. grounded: true only if every factual claim in the answer is supported by the "
    "retrieved context, OR the answer correctly declines / admits it doesn't have that "
    "information when the context doesn't support the question. False if the answer "
    "states specific facts (names, dates, materials) that are not present in the context.\n"
    "2. relevant: true if the answer actually addresses the visitor's question.\n"
    "Also give an overall score 1-5 (5 = excellent: grounded, on-topic, right length/tone; "
    "1 = hallucinated or off-topic).\n"
    'Respond ONLY with compact JSON: {"grounded": bool, "relevant": bool, "score": int, "explanation": "one sentence"}'
)


def llm_judge(client: OpenAI, question: str, mode: str, context: str, answer: str) -> dict:
    user_content = (
        f"Retrieved context:\n{context}\n\n"
        f"Mode: {mode}\n"
        f"Visitor question: {question}\n\n"
        f"Sophie's answer: {answer}"
    )
    try:
        resp = client.chat.completions.create(
            model=JUDGE_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001 — judge failure shouldn't crash the eval run
        return {"grounded": None, "relevant": None, "score": None, "explanation": f"judge_error: {exc}"}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(cases: list[dict], use_judge: bool = True, case_filter: str | None = None) -> list[dict]:
    rag = RAGEngine()
    client = OpenAI() if use_judge else None
    results = []

    for case in cases:
        if case_filter and case["id"] != case_filter:
            continue

        is_navigation = case["mode"] == "NAVIGATION"
        if is_navigation:
            # NAVIGATION is a deterministic dict lookup (qa_pipeline._navigation_answer),
            # not RAGEngine — go through the real production entry point so the eval
            # reflects what /ask actually returns, not the RAG fallback for that mode.
            qa_result = qa_run(
                question=case["question"], image_b64=None, rag=rag,
                mode="NAVIGATION", history=case.get("history"),
                known_exhibit=case.get("known_exhibit"),
            )
            result = {"answer": qa_result["answer"], "sources": []}
        else:
            result = rag.query(case["question"], mode=case["mode"], history=case.get("history"))

        det_checks = deterministic_checks(case, result)
        det_pass = all(det_checks.values()) if det_checks else True

        judge = None
        judge_pass = True
        # Skip the LLM-judge where it structurally can't give a useful verdict:
        # - NAVIGATION: a deterministic dict lookup can't hallucinate, and judging
        #   it against RAG exhibit context (which has no room data) would produce
        #   a false "ungrounded" verdict.
        # - expect_decline: the judge's "relevant" criterion penalizes an answer
        #   for not answering an out-of-scope question, which is the point.
        if use_judge and not is_navigation and not case.get("expect_decline"):
            history = case.get("history")
            if history:
                # Mirror rag_engine._query_with_history's retrieval query exactly,
                # otherwise the judge grades against different (stale/wrong) context
                # than what the system actually retrieved and answered from.
                recent = history[-_RETRIEVAL_HISTORY_WINDOW:]
                retrieval_query = " ".join(m["content"] for m in recent) + " " + case["question"]
            else:
                retrieval_query = case["question"]
            docs = rag._vectorstore.similarity_search(retrieval_query, k=2)
            context = "\n\n---\n\n".join(d.page_content for d in docs)
            judge = llm_judge(client, case["question"], case["mode"], context, result["answer"])
            if judge.get("score") is not None:
                judge_pass = bool(judge.get("grounded")) and judge["score"] >= 3

        results.append({
            "id": case["id"],
            "mode": case["mode"],
            "question": case["question"],
            "answer": result["answer"],
            "sources": result["sources"],
            "deterministic_checks": det_checks,
            "deterministic_pass": det_pass,
            "judge": judge,
            "judge_pass": judge_pass,
            "overall_pass": det_pass and judge_pass,
            "note": case.get("note"),
        })

    return results


def print_report(results: list[dict]) -> float:
    total = len(results)
    passed = sum(r["overall_pass"] for r in results)

    print(f"\n{'ID':<32} {'MODE':<18} {'DET':<5} {'JUDGE':<6} {'SCORE':<6} RESULT")
    print("-" * 90)
    for r in results:
        det = "PASS" if r["deterministic_pass"] else "FAIL"
        judge_score = r["judge"]["score"] if r["judge"] and r["judge"].get("score") is not None else "-"
        judge_state = "PASS" if r["judge_pass"] else "FAIL"
        overall = "PASS" if r["overall_pass"] else "FAIL"
        print(f"{r['id']:<32} {r['mode']:<18} {det:<5} {judge_state:<6} {str(judge_score):<6} {overall}")
        if not r["overall_pass"]:
            failed_checks = [k for k, v in r["deterministic_checks"].items() if not v]
            if failed_checks:
                print(f"    deterministic failures: {failed_checks}")
            if r["judge"] and not r["judge_pass"]:
                print(f"    judge: {r['judge'].get('explanation')}")
            if r["note"]:
                print(f"    note: {r['note']}")
    print("-" * 90)
    rate = passed / total if total else 0.0
    print(f"Pass rate: {passed}/{total} ({rate:.0%})\n")
    return rate


def save_results(results: list[dict], pass_rate: float) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"{ts}.json"
    with open(path, "w") as f:
        json.dump({"timestamp": ts, "pass_rate": pass_rate, "results": results}, f, indent=2)
    print(f"Results saved to {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="ContextAR RAG eval harness")
    parser.add_argument("--no-judge", action="store_true",
                        help="skip LLM-judge scoring (deterministic checks only)")
    parser.add_argument("--case", type=str, default=None, help="run a single case by id")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="exit 1 if pass rate is below this threshold (0-1), for CI gating")
    parser.add_argument("--no-save", action="store_true", help="don't write a results JSON file")
    args = parser.parse_args()

    cases = load_cases()
    results = run(cases, use_judge=not args.no_judge, case_filter=args.case)
    if not results:
        print(f"No matching cases found (filter={args.case!r})")
        sys.exit(1)

    pass_rate = print_report(results)
    if not args.no_save:
        save_results(results, pass_rate)

    if args.fail_under is not None and pass_rate < args.fail_under:
        print(f"FAIL: pass rate {pass_rate:.0%} is below threshold {args.fail_under:.0%}")
        sys.exit(1)


if __name__ == "__main__":
    main()
