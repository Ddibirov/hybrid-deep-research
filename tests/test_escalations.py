"""Tests for escalations.py (structured human escalation)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import escalations  # noqa: E402


def make_registry(tmp: Path) -> Path:
    p = tmp / "source_registry.json"
    p.write_text(json.dumps({
        "version": 1, "frozen": True, "sources": [
            {"id": "S1", "url": "https://a.example.com", "canonical_url": "https://a.example.com", "source_type": "news"},
            {"id": "S2", "url": "https://b.example.com", "canonical_url": "https://b.example.com", "source_type": "blog"},
        ],
    }), encoding="utf-8")
    return p


def write_claims(tmp: Path, claims: list[dict]) -> Path:
    p = tmp / "claims.jsonl"
    lines = [json.dumps({"_meta": {"version": 1, "frozen": True}})]
    lines.extend(json.dumps(c, ensure_ascii=False) for c in claims)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def make_verdicts(tmp: Path, verdicts: dict) -> Path:
    p = tmp / "claim_verification.json"
    p.write_text(json.dumps({
        "verdicts": len(verdicts), "verdicts_detail": verdicts,
        "refuted": sum(1 for v in verdicts.values() if v.get("verdict") == "refuted"),
        "not_found": sum(1 for v in verdicts.values() if v.get("verdict") == "not_found"),
    }), encoding="utf-8")
    return p


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = make_registry(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_when_all_supported(self):
        claims_path = write_claims(Path(self.tmp.name), [
            {"id": "C1", "claim": "X is true", "importance": "high", "confidence": "high",
             "evidence": [{"source_id": "S1"}]},
        ])
        fc = make_verdicts(Path(self.tmp.name), {
            "C1": {"verdict": "supported", "rationale": "ok"},
        })
        result = escalations.build(claims_path, self.reg, fc)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["escalations"], [])

    def test_refuted_forces_needs_review(self):
        claims_path = write_claims(Path(self.tmp.name), [
            {"id": "C1", "claim": "X is true", "importance": "high", "confidence": "high",
             "evidence": [{"source_id": "S1"}]},
        ])
        fc = make_verdicts(Path(self.tmp.name), {
            "C1": {"verdict": "refuted", "rationale": "page says the opposite"},
        })
        result = escalations.build(claims_path, self.reg, fc)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(len(result["escalations"]), 1)
        self.assertEqual(result["escalations"][0]["claim_id"], "C1")
        self.assertIn("refuted", result["escalations"][0]["reasons"])
        self.assertEqual(result["escalations"][0]["recommended_action"], "re-anchor")

    def test_not_found_is_review_recommended(self):
        claims_path = write_claims(Path(self.tmp.name), [
            {"id": "C1", "claim": "X is true", "importance": "high", "confidence": "medium",
             "evidence": [{"source_id": "S1"}]},
        ])
        fc = make_verdicts(Path(self.tmp.name), {
            "C1": {"verdict": "not_found", "rationale": "page does not address"},
        })
        result = escalations.build(claims_path, self.reg, fc)
        self.assertEqual(result["status"], "review_recommended")

    def test_numeric_mismatch_flags(self):
        claims_path = write_claims(Path(self.tmp.name), [
            {"id": "C1", "claim": "Price is $99 per month", "importance": "high", "confidence": "high",
             "evidence": [{"source_id": "S1"}]},
        ])
        fc = make_verdicts(Path(self.tmp.name), {
            "C1": {"verdict": "supported",
                   "numeric_check": {"match": "mismatch", "claimed": ["99"], "found": ["199"]}},
        })
        result = escalations.build(claims_path, self.reg, fc)
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("numeric_mismatch", result["escalations"][0]["reasons"])

    def test_low_confidence_escalated(self):
        claims_path = write_claims(Path(self.tmp.name), [
            {"id": "C1", "claim": "X maybe true", "importance": "high", "confidence": "low",
             "evidence": [{"source_id": "S1"}]},
        ])
        result = escalations.build(claims_path, self.reg, None)
        self.assertEqual(result["status"], "review_recommended")
        self.assertIn("low_confidence", result["escalations"][0]["reasons"])


class TestCLI(unittest.TestCase):
    def test_cli_writes_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp)
            claims_path = write_claims(tmp, [
                {"id": "C1", "claim": "X is true", "importance": "high", "confidence": "low",
                 "evidence": [{"source_id": "S1"}]},
            ])
            out = tmp / "escalations.json"
            rc = subprocess.run(
                [sys.executable, str(SCRIPTS / "escalations.py"), str(claims_path),
                 "--registry", str(reg_path), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("escalations", data)


if __name__ == "__main__":
    unittest.main()
