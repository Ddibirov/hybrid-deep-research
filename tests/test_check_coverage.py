"""Tests for check_coverage.py (coverage assertions)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_coverage  # noqa: E402


def make_registry(tmp: Path, sources: list[dict]) -> Path:
    p = tmp / "source_registry.json"
    p.write_text(json.dumps({"version": 1, "frozen": True, "sources": sources}), encoding="utf-8")
    return p


def write_claims(tmp: Path, claims: list[dict]) -> Path:
    p = tmp / "claims.jsonl"
    lines = [json.dumps({"_meta": {"version": 1, "frozen": True}})]
    lines.extend(json.dumps(c, ensure_ascii=False) for c in claims)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class TestDomainOf(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(check_coverage.domain_of("https://news.example.com/story"), "example.com")

    def test_www(self):
        self.assertEqual(check_coverage.domain_of("https://www.bbc.com/x"), "bbc.com")

    def test_co_uk(self):
        self.assertEqual(check_coverage.domain_of("https://www.example.co.uk/x"), "co.uk")

    def test_port_stripped(self):
        self.assertEqual(check_coverage.domain_of("https://example.com:8080/x"), "example.com")


class TestCheckClaims(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sources = {
            "S1": {"id": "S1", "url": "https://news.example.com/story", "canonical_url": "https://news.example.com/story", "source_type": "news"},
            "S2": {"id": "S2", "url": "https://blog.example.net/post", "canonical_url": "https://blog.example.net/post", "source_type": "blog"},
            "S3": {"id": "S3", "url": "https://news.example.com/mirror", "canonical_url": "https://news.example.com/mirror", "source_type": "news"},
            "S4": {"id": "S4", "url": "https://docs.example.org", "canonical_url": "https://docs.example.org", "source_type": "official_docs"},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_domains_pass(self):
        claims = [{"id": "C1", "importance": "high", "confidence": "high",
                   "evidence": [{"source_id": "S1"}, {"source_id": "S4"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(gaps, [])

    def test_mirrors_same_domain_fail(self):
        claims = [{"id": "C1", "importance": "high", "confidence": "medium",
                   "evidence": [{"source_id": "S1"}, {"source_id": "S3"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["rule"], "domain_independence")

    def test_single_source_not_flagged_domain(self):
        claims = [{"id": "C1", "importance": "high", "confidence": "medium",
                   "evidence": [{"source_id": "S1"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(gaps, [])

    def test_high_confidence_without_primary_fails(self):
        claims = [{"id": "C1", "importance": "high", "confidence": "high",
                   "evidence": [{"source_id": "S1"}, {"source_id": "S2"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["rule"], "primary_source_preference")

    def test_high_confidence_with_primary_passes(self):
        claims = [{"id": "C1", "importance": "high", "confidence": "high",
                   "evidence": [{"source_id": "S1"}, {"source_id": "S4"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(gaps, [])

    def test_low_importance_skipped(self):
        claims = [{"id": "C1", "importance": "medium", "confidence": "high",
                   "evidence": [{"source_id": "S1"}]}]
        gaps = check_coverage.check_claims(claims, self.sources)
        self.assertEqual(gaps, [])


class TestSuccessCriteria(unittest.TestCase):
    def test_criterion_missing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            brief = tmp / "brief.json"
            brief.write_text(json.dumps({"success_criteria": ["Compare pricing tiers of tools"]}), encoding="utf-8")
            claims = [{"id": "C1", "claim": "Odysseus architecture"}]
            gaps = check_coverage.check_success_criteria(brief, claims, {})
            self.assertEqual(len(gaps), 1)

    def test_criterion_present(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            brief = tmp / "brief.json"
            brief.write_text(json.dumps({"success_criteria": ["Compare pricing tiers of tools"]}), encoding="utf-8")
            claims = [{"id": "C1", "claim": "Tavily pricing tiers comparison"}]
            gaps = check_coverage.check_success_criteria(brief, claims, {})
            self.assertEqual(gaps, [])

    def test_no_brief(self):
        gaps = check_coverage.check_success_criteria(None, [], {})
        self.assertEqual(gaps, [])


class TestCLI(unittest.TestCase):
    def test_coverage_gap_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp, [
                {"id": "S1", "url": "https://news.example.com/story", "canonical_url": "https://news.example.com/story", "source_type": "news"},
                {"id": "S2", "url": "https://news.example.com/2", "canonical_url": "https://news.example.com/2", "source_type": "news"},
            ])
            claims_path = write_claims(tmp, [
                {"id": "C1", "importance": "high", "confidence": "medium",
                 "evidence": [{"source_id": "S1"}, {"source_id": "S2"}]},
            ])
            out = tmp / "coverage.json"
            rc = subprocess.run(
                [sys.executable, str(SCRIPTS / "check_coverage.py"), str(claims_path),
                 "--registry", str(reg_path), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(rc.returncode, 1)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "coverage_gap")

    def test_clean_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp, [
                {"id": "S1", "url": "https://news.example.com/story", "canonical_url": "https://news.example.com/story", "source_type": "news"},
                {"id": "S2", "url": "https://blog.example.net/post", "canonical_url": "https://blog.example.net/post", "source_type": "news"},
            ])
            claims_path = write_claims(tmp, [
                {"id": "C1", "importance": "high", "confidence": "medium",
                 "evidence": [{"source_id": "S1"}, {"source_id": "S2"}]},
            ])
            out = tmp / "coverage.json"
            rc = subprocess.run(
                [sys.executable, str(SCRIPTS / "check_coverage.py"), str(claims_path),
                 "--registry", str(reg_path), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "pass")


if __name__ == "__main__":
    unittest.main()
