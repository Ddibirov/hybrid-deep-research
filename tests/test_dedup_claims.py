"""Tests for dedup_claims.py (deterministic dedup)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dedup_claims  # noqa: E402


def make_registry(tmp: Path) -> Path:
    reg = {
        "version": 1, "frozen": True, "sources": [
            {"id": "S1", "url": "https://a.example.com", "canonical_url": "https://a.example.com", "source_type": "news"},
            {"id": "S2", "url": "https://b.example.com", "canonical_url": "https://b.example.com", "source_type": "blog"},
            {"id": "S3", "url": "https://c.example.com", "canonical_url": "https://c.example.com", "source_type": "official_docs"},
        ],
    }
    p = tmp / "source_registry.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    return p


def write_claims(tmp: Path, claims: list[dict]) -> Path:
    p = tmp / "claims.jsonl"
    lines = [json.dumps({"_meta": {"version": 1, "frozen": True}})]
    lines.extend(json.dumps(c, ensure_ascii=False) for c in claims)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class TestExtractNumbers(unittest.TestCase):
    def test_commas_and_decimals(self):
        self.assertEqual(dedup_claims.extract_numbers("28,929 stars and 3.5%"), {"28929", "3.5"})

    def test_no_numbers(self):
        self.assertEqual(dedup_claims.extract_numbers("no digits here"), set())


class TestNormalizeText(unittest.TestCase):
    def test_case_and_punct(self):
        self.assertEqual(dedup_claims.normalize_text("  Hello, World!  "), "hello world")


class TestIsDuplicate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = dedup_claims.load_registry(make_registry(Path(self.tmp.name)))

    def tearDown(self):
        self.tmp.cleanup()

    def _claim(self, cid, text, sources, importance="medium"):
        return {"id": cid, "claim": text, "importance": importance,
                "evidence": [{"source_id": s} for s in sources]}

    def test_identical_text(self):
        a = self._claim("C1", "Odysseus has 85k stars", ["S1"])
        b = self._claim("C2", "Odysseus has 85k stars", ["S1"])
        is_dup, reason = dedup_claims.is_duplicate(a, b, self.registry)
        self.assertTrue(is_dup)
        self.assertIn("identical", reason)

    def test_same_number_overlapping_sources(self):
        a = self._claim("C1", "Tavily costs $0 per month on free tier", ["S1", "S2"])
        b = self._claim("C2", "Tavily free tier is $0 monthly", ["S1", "S3"])
        is_dup, reason = dedup_claims.is_duplicate(a, b, self.registry)
        self.assertTrue(is_dup)
        self.assertIn("same numbers", reason)

    def test_high_importance_source_overlap(self):
        a = self._claim("C1", "Framework X is the most active", ["S1", "S2", "S3"], importance="high")
        b = self._claim("C2", "Framework X maintains steady releases", ["S1", "S2", "S3"], importance="high")
        is_dup, reason = dedup_claims.is_duplicate(a, b, self.registry)
        self.assertTrue(is_dup)

    def test_different_topics_not_dup(self):
        a = self._claim("C1", "Odysseus has 85k stars", ["S1"])
        b = self._claim("C2", "Firecrawl parses markdown", ["S2"])
        is_dup, _ = dedup_claims.is_duplicate(a, b, self.registry)
        self.assertFalse(is_dup)


class TestDedup(unittest.TestCase):
    def test_keeps_stronger_claim(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp)
            claims_path = write_claims(tmp, [
                {"id": "C1", "claim": "Odysseus has 85k stars", "importance": "medium",
                 "evidence": [{"source_id": "S1"}]},
                {"id": "C2", "claim": "Odysseus has 85k stars", "importance": "medium",
                 "evidence": [{"source_id": "S2"}]},
            ])
            result = dedup_claims.dedup(claims_path, reg_path)
            self.assertEqual(result["duplicates_found"], 1)
            # S1 is news (0.7) > S2 blog (0.4) → C1 kept
            self.assertEqual(result["duplicates"][0]["kept"], "C1")
            self.assertEqual(result["duplicates"][0]["dropped"], "C2")

    def test_no_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp)
            claims_path = write_claims(tmp, [
                {"id": "C1", "claim": "Odysseus has 85k stars", "importance": "medium",
                 "evidence": [{"source_id": "S1"}]},
                {"id": "C2", "claim": "Firecrawl parses markdown", "importance": "medium",
                 "evidence": [{"source_id": "S2"}]},
            ])
            result = dedup_claims.dedup(claims_path, reg_path)
            self.assertEqual(result["duplicates_found"], 0)


class TestCLI(unittest.TestCase):
    def test_cli_runs(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp)
            claims_path = write_claims(tmp, [
                {"id": "C1", "claim": "Same text here", "importance": "medium",
                 "evidence": [{"source_id": "S1"}]},
                {"id": "C2", "claim": "Same text here", "importance": "medium",
                 "evidence": [{"source_id": "S2"}]},
            ])
            out = tmp / "dedup.json"
            rc = subprocess.run(
                [sys.executable, str(SCRIPTS / "dedup_claims.py"), str(claims_path),
                 "--registry", str(reg_path), "--out", str(out)],
                capture_output=True, text=True)
            self.assertEqual(rc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["duplicates_found"], 1)

    def test_missing_claims(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg_path = make_registry(tmp)
            rc = subprocess.run(
                [sys.executable, str(SCRIPTS / "dedup_claims.py"), str(tmp / "nope.jsonl"),
                 "--registry", str(reg_path), "--out", str(tmp / "out.json")],
                capture_output=True, text=True)
            self.assertEqual(rc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
