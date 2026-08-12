"""Tests for annotate_report.py — claim-marker auto-annotation."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import annotate_report  # noqa: E402

SAMPLE = """---
status: pending
topic: test
sources_count: 2
---

# Test

First finding claim [S1]. <!-- claims: C1 -->

## Sources

[S1] One — https://one.example.com (2026, web)
[S2] Two — https://two.example.com (2026, web)
"""


def make_claims(tmp: Path) -> Path:
    p = tmp / "claims.jsonl"
    claims = [
        {"id": "C1", "claim": "c1", "evidence": [{"source_id": "S1", "support": "direct"}]},
        {"id": "C2", "claim": "c2", "evidence": [{"source_id": "S2", "support": "direct"}]},
    ]
    p.write_text("\n".join(json.dumps(c) for c in claims) + "\n", encoding="utf-8")
    return p


class TestAnnotate(unittest.TestCase):
    def test_preserves_sources_heading(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            claims = make_claims(tmp)
            warnings, out = annotate_report.annotate(SAMPLE, annotate_report.load_claim_evidence(claims))
            self.assertEqual(warnings, [])
            self.assertIn("## Sources", out)
            self.assertIn("[S1] One", out)

    def test_marks_unannotated_block(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            claims = make_claims(tmp)
            sample = SAMPLE.replace("<!-- claims: C1 -->", "")
            warnings, out = annotate_report.annotate(sample, annotate_report.load_claim_evidence(claims))
            self.assertEqual(warnings, [])
            self.assertIn("<!-- claims: C1 -->", out)

    def test_marker_not_glued_to_sources_heading(self):
        # regression: a marker added to the LAST narrative line used to end up as
        # `<!-- claims: C1 -->## Sources` because the narrative join had no trailing newline
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            claims = make_claims(tmp)
            sample = SAMPLE.replace("<!-- claims: C1 -->", "")
            warnings, out = annotate_report.annotate(sample, annotate_report.load_claim_evidence(claims))
            self.assertEqual(warnings, [])
            self.assertNotIn("-->## Sources", out)
            self.assertNotIn("-->\n## Sources", out)
            self.assertRegex(out, r"-->\n\n## Sources")

    def test_warns_when_no_claim_matches(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            claims = make_claims(tmp)
            sample = SAMPLE.replace(
                "First finding claim [S1]. <!-- claims: C1 -->",
                "Claim [S9] unknown source.",
            )
            warnings, _ = annotate_report.annotate(sample, annotate_report.load_claim_evidence(claims))
            self.assertTrue(any("no claim matches" in w for w in warnings))

    def test_cli_dry_run_no_write(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            claims = make_claims(tmp)
            report = tmp / "report.md"
            report.write_text(SAMPLE, encoding="utf-8")
            before = report.read_text(encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / "annotate_report.py"), str(report), "--claims", str(claims)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Dry-run", r.stdout)
            self.assertEqual(report.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
