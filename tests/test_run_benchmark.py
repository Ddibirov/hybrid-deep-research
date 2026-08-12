"""Tests for run_benchmark.py — benchmark runner, baseline tracking, degradation."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_benchmark  # noqa: E402
from test_fact_check import make_run  # noqa: E402


class TestRunBenchmark(unittest.TestCase):
    def test_prepare_creates_brief(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc = run_benchmark.prepare("software-01", tmp / "run", "surface", Path(__file__).parent.parent / "evals" / "questions.json")
            self.assertEqual(rc, 0)
            brief = json.loads((tmp / "run" / "brief.json").read_text())
            self.assertEqual(brief["question_id"], "software-01")
            self.assertEqual(brief["depth"], "surface")

    def test_prepare_unknown_question(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rc = run_benchmark.prepare("nope-99", tmp / "run", "surface", Path(__file__).parent.parent / "evals" / "questions.json")
            self.assertEqual(rc, 2)

    def test_score_and_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = tmp / "bench-software-01"
            make_run(run)
            baseline = tmp / "baseline.json"
            rc = run_benchmark.score([run], baseline, False)
            self.assertEqual(rc, 0)
            self.assertTrue(baseline.exists())
            data = json.loads(baseline.read_text())
            self.assertEqual(len(data["entries"]), 1)
            self.assertIn("bench-software-01", data["entries"][0]["runs"])

    def test_score_detects_degradation(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = tmp / "bench-software-01"
            make_run(run)
            baseline = tmp / "baseline.json"
            self.assertEqual(run_benchmark.score([run], baseline, False), 0)
            # corrupt the report: remove all citations -> citation_coverage drops
            report = run / "report.md"
            text = report.read_text()
            text = text.replace("Claim one [S1]. <!-- claims: C1 -->", "Claim one. <!-- claims: C1 -->")
            text = text.replace("Claim two [S2]. <!-- claims: C2 -->", "Claim two. <!-- claims: C2 -->")
            report.write_text(text)
            rc = run_benchmark.score([run], baseline, False)
            self.assertEqual(rc, 1)
            data = json.loads(baseline.read_text())
            self.assertEqual(len(data["entries"]), 2)

    def test_baseline_table(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = tmp / "bench-software-01"
            make_run(run)
            baseline = tmp / "baseline.json"
            run_benchmark.score([run], baseline, False)
            rc = run_benchmark.baseline(baseline, False)
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
