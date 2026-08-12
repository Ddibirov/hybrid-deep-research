#!/usr/bin/env python3
"""Benchmark runner: turn evals/questions.json entries into reproducible runs and track a baseline.

The full research pipeline is LLM work (search + synthesis + verification), so this
script does the deterministic parts around it:

  prepare  — pick a question from evals/questions.json, create a run directory
             with a ready brief (saves the Prompt Master step in the agent run):
    python3 scripts/run_benchmark.py prepare --question software-01 \
        --out .hybrid-research/bench-software-01 [--depth surface|moderate|exhaustive]

  score    — after the run finished, aggregate benchmark.py quality metrics +
             eval_citations.py triad scores for one or more run dirs, and append
             to a baseline file:
    python3 scripts/run_benchmark.py score \
        --runs .hybrid-research/bench-software-01 \
        --baseline .hybrid-research/benchmark-results.json [--json]

  baseline — print the current baseline table (run id, date, key metrics):
    python3 scripts/run_benchmark.py baseline \
        --baseline .hybrid-research/benchmark-results.json

Exit codes: 0 ok; 1 score degraded vs baseline (same run id, any metric down);
2 usage error / missing inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import benchmark
import eval_citations

EVALS = Path(__file__).resolve().parent.parent / "evals" / "questions.json"
KEY_METRICS = (
    "validated", "semantic_pass", "structural_pass", "citation_coverage",
    "claim_marker_coverage", "primary_source_ratio", "source_access_health",
    "budget_utilization",
)
RUBRIC_METRICS = (
    "rubric_factual_accuracy", "rubric_breadth_depth", "rubric_presentation",
    "rubric_primary_source", "rubric_negative_hallucination", "rubric_total",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("questions", [])


def prepare(question_id: str, out: Path, depth: str, evals_path: Path, light: bool = False) -> int:
    questions = load_questions(evals_path)
    match = next((q for q in questions if q.get("id") == question_id), None)
    if not match:
        print(f"ERROR: question {question_id!r} not found in {evals_path}", file=sys.stderr)
        return 2
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    brief = {
        "question_id": match["id"],
        "category": match.get("category", "general"),
        "prompt": match["prompt"],
        "time_sensitivity": match.get("time_sensitivity", "medium"),
        "expected_source_classes": match.get("expected_source_classes", []),
        "depth": depth,
        "light": light,
        "prepared_at": _utcnow(),
        "status": "prepared",
    }
    (out / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared run: {out}")
    print(f"  question: {match['id']} ({match.get('category','general')})")
    print(f"  prompt:   {match['prompt'][:100]}{'...' if len(match['prompt'])>100 else ''}")
    print(f"  depth:    {depth}{'  [LIGHT: no falsification round, no LLM fact-check judges]' if light else ''}")
    print("Run the research pipeline on this brief, then call: run_benchmark.py score --runs " + str(out))
    return 0


def _run_scores(runs: list[Path]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for run in runs:
        run = Path(run)
        rid = run.name
        bm = benchmark.score_run(run)
        tri = {}
        try:
            eval_citations.score(run, None, None, None, None)
            tri_path = run / "eval_citations.json"
            if tri_path.exists():
                tri = json.loads(tri_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — scoring must not kill the batch
            tri = {"error": str(exc)}
        result[rid] = {"run_dir": str(run), "benchmark": bm, "triad": tri}
    return result


def score(runs: list[Path], baseline_path: Path, print_json: bool) -> int:
    if not runs:
        print("ERROR: --runs required", file=sys.stderr)
        return 2
    missing = [r for r in runs if not Path(r).is_dir()]
    if missing:
        print(f"ERROR: run dirs not found: {missing}", file=sys.stderr)
        return 2

    scores = _run_scores(runs)
    entry = {"scored_at": _utcnow(), "runs": scores}
    baseline_path = Path(baseline_path)
    history = []
    if baseline_path.exists():
        try:
            history = json.loads(baseline_path.read_text(encoding="utf-8"))
            if isinstance(history, dict):
                history = history.get("entries", [])
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    baseline_path.write_text(
        json.dumps({"entries": history}, ensure_ascii=False, indent=2), encoding="utf-8")

    if print_json:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0

    degraded = 0
    for rid, data in scores.items():
        bm = data["benchmark"]
        tri = data["triad"]
        print(f"== {rid} ==")
        for key in KEY_METRICS:
            if key in bm:
                print(f"  {key}: {bm[key]}")
        if "link_works" in tri and tri["link_works"]:
            lw = tri["link_works"]
            print(f"  triad.link_works: {lw.get('rate')}")
        if "relevant_content" in tri and tri["relevant_content"]:
            rc = tri["relevant_content"]
            print(f"  triad.relevant: {rc.get('rate')}")
        if "fact_check" in tri and tri["fact_check"]:
            fc = tri["fact_check"]
            print(f"  triad.fact_check: {fc.get('rate')}")
        for key in RUBRIC_METRICS:
            if key in bm:
                print(f"  {key}: {bm[key]}")

        prev = _previous_same_run(history, rid)
        if prev:
            for key in KEY_METRICS + RUBRIC_METRICS:
                pv = prev.get("benchmark", {}).get(key)
                cv = bm.get(key)
                if isinstance(pv, (int, float)) and isinstance(cv, (int, float)) and cv < pv - 1e-9:
                    print(f"  DEGRADED {key}: {cv} < previous {pv}", file=sys.stderr)
                    degraded = 1
    print(f"\nBaseline saved: {baseline_path} ({len(history)} entries)")
    return degraded


def _previous_same_run(history: list[dict], run_id: str) -> dict | None:
    for entry in reversed(history[:-1]):
        if run_id in entry.get("runs", {}):
            return entry["runs"][run_id]
    return None


def baseline(baseline_path: Path, print_json: bool) -> int:
    if not Path(baseline_path).exists():
        print(f"ERROR: baseline not found: {baseline_path}", file=sys.stderr)
        return 2
    history = json.loads(Path(baseline_path).read_text(encoding="utf-8")).get("entries", [])
    if print_json:
        print(json.dumps(history, ensure_ascii=False, indent=2))
        return 0
    print(f"{'run':<28} {'date':<22} {'validated':>9} {'citation':>9} {'access':>9} {'factcheck':>9}")
    for entry in history:
        for rid, data in entry.get("runs", {}).items():
            bm = data.get("benchmark", {})
            tri = data.get("triad", {})
            fc = tri.get("fact_check") or {}
            print(f"{rid:<28} {entry.get('scored_at','')[:19]:<22} "
                  f"{str(bm.get('validated','-')):>9} {str(bm.get('citation_coverage','-')):>9} "
                  f"{str(bm.get('source_access_health','-')):>9} {str(fc.get('rate','-')):>9}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("--question", required=True)
    p_prep.add_argument("--out", type=Path, required=True)
    p_prep.add_argument("--depth", default="surface", choices=["surface", "moderate", "exhaustive"])
    p_prep.add_argument("--light", action="store_true", help="skip falsification round and LLM fact-check judges (cheap benchmark runs)")
    p_prep.add_argument("--evals", type=Path, default=EVALS)

    p_score = sub.add_parser("score")
    p_score.add_argument("--runs", nargs="+", type=Path, required=True)
    p_score.add_argument("--baseline", type=Path, required=True)
    p_score.add_argument("--json", action="store_true")

    p_base = sub.add_parser("baseline")
    p_base.add_argument("--baseline", type=Path, required=True)
    p_base.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return prepare(args.question, args.out, args.depth, args.evals, args.light)
    if args.command == "score":
        return score(args.runs, args.baseline, args.json)
    return baseline(args.baseline, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
