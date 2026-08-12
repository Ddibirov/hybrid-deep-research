"""Tests for fact_check_claims.py + eval_citations.py (arXiv citation triad)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fact_check_claims  # noqa: E402
import eval_citations  # noqa: E402


def make_run(tmp: Path) -> dict:
    """Registry + claims + report + access + verdicts, mirroring a finished run."""
    tmp.mkdir(parents=True, exist_ok=True)
    registry = {
        "version": 1, "frozen": True, "sources": [
            {"id": "S1", "title": "One", "url": "https://one.example.com",
             "canonical_url": "https://one.example.com", "source_type": "web"},
            {"id": "S2", "title": "Two", "url": "https://two.example.com",
             "canonical_url": "https://two.example.com", "source_type": "web"},
        ],
    }
    (tmp / "source_registry.json").write_text(json.dumps(registry), encoding="utf-8")

    claims = [
        {"id": "C1", "claim": "One supports X", "confidence": "high",
         "evidence": [{"source_id": "S1", "support": "direct"}]},
        {"id": "C2", "claim": "Two says Y", "confidence": "medium",
         "evidence": [{"source_id": "S2", "support": "direct"}]},
    ]
    lines = [json.dumps({"_meta": {"version": 1, "frozen": True}})] + [json.dumps(c) for c in claims]
    (tmp / "claims.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = """---
status: validated
---
# T

Claim one [S1]. <!-- claims: C1 -->
Claim two [S2]. <!-- claims: C2 -->

## Sources

[S1] One — https://one.example.com
[S2] Two — https://two.example.com
"""
    (tmp / "report.md").write_text(report, encoding="utf-8")

    access = {"version": 1, "sources": {
        "S1": {"status": "ok", "http_code": 200},
        "S2": {"status": "restricted", "http_code": 403},
    }}
    (tmp / "source_access.json").write_text(json.dumps(access), encoding="utf-8")

    return {"registry": registry, "claims": claims}


class TestFactCheckClaims(unittest.TestCase):
    def test_prepare_creates_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            out = tmp / "fc"
            rc = fact_check_claims.prepare(tmp / "claims.jsonl", tmp / "source_registry.json", out)
            self.assertEqual(rc, 0)
            self.assertTrue((out / "tasks" / "C1.json").exists())
            task = json.loads((out / "tasks" / "C1.json").read_text())
            self.assertEqual(task["evidence_sources"][0]["source_id"], "S1")
            self.assertEqual(task["evidence_sources"][0]["url"], "https://one.example.com")

    def test_collect_exit_zero_all_supported(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            verdicts = tmp / "v"
            verdicts.mkdir()
            for cid, verdict in [("C1", "supported"), ("C2", "supported")]:
                (verdicts / f"{cid}.json").write_text(json.dumps({
                    "claim_id": cid, "verdict": verdict, "rationale": "ok",
                    "evidence_source_id": "S1" if cid == "C1" else "S2",
                }))
            out = tmp / "claim_verification.json"
            rc = fact_check_claims.collect(tmp / "claims.jsonl", verdicts, out)
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text())
            self.assertEqual(data["supported"], 2)

    def test_collect_exit_one_on_refuted(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            verdicts = tmp / "v"
            verdicts.mkdir()
            (verdicts / "C1.json").write_text(json.dumps({
                "claim_id": "C1", "verdict": "refuted", "rationale": "page contradicts",
                "evidence_source_id": "S1",
            }))
            out = tmp / "claim_verification.json"
            rc = fact_check_claims.collect(tmp / "claims.jsonl", verdicts, out)
            self.assertEqual(rc, 1)
            data = json.loads(out.read_text())
            self.assertEqual(data["refuted"], 1)

    def test_collect_flags_missing_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            verdicts = tmp / "v"
            verdicts.mkdir()
            out = tmp / "claim_verification.json"
            rc = fact_check_claims.collect(tmp / "claims.jsonl", verdicts, out)
            self.assertEqual(rc, 1)
            data = json.loads(out.read_text())
            self.assertEqual(sorted(data["missing_verdicts"]), ["C1", "C2"])

    def test_prepare_extracts_claimed_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            out = tmp / "fc"
            fact_check_claims.prepare(tmp / "claims.jsonl", tmp / "source_registry.json", out)
            # C1 has no numbers
            task = json.loads((out / "tasks" / "C1.json").read_text())
            self.assertEqual(task["claimed_numbers"], [])

    def test_collect_numeric_precision(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            verdicts = tmp / "v"
            verdicts.mkdir()
            (verdicts / "C1.json").write_text(json.dumps({
                "claim_id": "C1", "verdict": "supported", "rationale": "ok",
                "evidence_source_id": "S1",
                "numeric_check": {"match": "match", "claimed": ["99"], "found": ["99"]},
            }))
            (verdicts / "C2.json").write_text(json.dumps({
                "claim_id": "C2", "verdict": "supported", "rationale": "ok",
                "evidence_source_id": "S2",
                "numeric_check": {"match": "none", "claimed": [], "found": []},
            }))
            out = tmp / "claim_verification.json"
            fact_check_claims.collect(tmp / "claims.jsonl", verdicts, out)
            data = json.loads(out.read_text())
            self.assertIn("numeric_precision", data)

    def test_collect_rejects_invalid_numeric_check(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            verdicts = tmp / "v"
            verdicts.mkdir()
            (verdicts / "C1.json").write_text(json.dumps({
                "claim_id": "C1", "verdict": "supported", "rationale": "ok",
                "evidence_source_id": "S1",
                "numeric_check": {"match": "bogus"},
            }))
            out = tmp / "claim_verification.json"
            rc = fact_check_claims.collect(tmp / "claims.jsonl", verdicts, out)
            self.assertEqual(rc, 1)
            data = json.loads(out.read_text())
            self.assertTrue(any("numeric_check" in p for p in data["problems"]))


class TestEvalCitations(unittest.TestCase):
    def test_score_all_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            # fake fact-check output
            (tmp / "claim_verification.json").write_text(json.dumps({
                "verdicts": 2, "supported": 1, "refuted": 1, "not_found": 0,
            }), encoding="utf-8")
            rc = eval_citations.score(tmp, None, None, None, None)
            self.assertEqual(rc, 0)
            data = json.loads((tmp / "eval_citations.json").read_text())
            self.assertEqual(data["link_works"]["ok_or_restricted"], 2)
            self.assertEqual(data["link_works"]["checked"], 2)
            self.assertEqual(data["relevant_content"]["cited_in_report"], 2)
            self.assertEqual(data["fact_check"]["supported"], 1)

    def test_score_reports_numeric_precision(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            (tmp / "claim_verification.json").write_text(json.dumps({
                "verdicts": 2, "supported": 2, "refuted": 0, "not_found": 0,
                "numeric_precision": {"claims_with_numbers": 2, "exact": 1, "rate": 0.5},
            }), encoding="utf-8")
            eval_citations.score(tmp, None, None, None, None)
            data = json.loads((tmp / "eval_citations.json").read_text())
            self.assertEqual(data["fact_check"]["numeric_precision"]["rate"], 0.5)

    def test_cli_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            make_run(tmp)
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / "eval_citations.py"), str(tmp)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Link Works", r.stdout)


if __name__ == "__main__":
    unittest.main()
