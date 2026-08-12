import json,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class BenchmarkTests(unittest.TestCase):
    def make_run(self,root,status='validated'):
        d=Path(root)/'run'; d.mkdir(parents=True)
        (d/'report_manifest.json').write_text(json.dumps({'status':status,'semantic_verification':'passed','structural_validation':'passed','evaluation':{'factual_precision':0.9,'completeness':0.8}}))
        (d/'source_registry.json').write_text(json.dumps({'sources':[{'id':'S1','url':'https://example.com','source_type':'official_docs'},{'id':'S2','url':'https://example.org','source_type':'news'}]}))
        (d/'claims.jsonl').write_text('\n'.join([json.dumps({'_meta':{'frozen':True}}),json.dumps({'id':'C1','importance':'critical','verification':'supported'}),json.dumps({'id':'C2','importance':'medium','verification':'unverified'})])+'\n')
        (d/'state.json').write_text(json.dumps({'budget':{'query_calls':8,'query_limit':16,'fetch_calls':4,'fetch_limit':16,'investigator_calls':4,'investigator_limit':8}}))
        (d/'source_access.json').write_text(json.dumps({'sources':{'S1':{'status':'ok'},'S2':{'status':'restricted'}}}))
        (d/'report.md').write_text('''---\nstatus: validated\nsources_count: 2\n---\n# Report\n\nA claim [S1] <!-- claims:C1 -->\n\n- Another [S2] <!-- claims:C2 -->\n\n## Sources\n[S1] A — https://example.com\n[S2] B — https://example.org\n''')
        return d

    def test_score_run_metrics(self):
        from benchmark import score_run
        with tempfile.TemporaryDirectory() as tmp:
            score=score_run(self.make_run(tmp))
            self.assertEqual(score['validated'],1.0); self.assertEqual(score['citation_coverage'],1.0); self.assertEqual(score['claim_marker_coverage'],1.0); self.assertEqual(score['primary_source_ratio'],0.5); self.assertEqual(score['source_access_health'],0.5); self.assertEqual(score['unresolved_critical_claims'],0); self.assertAlmostEqual(score['budget_utilization'],0.5); self.assertEqual(score['factual_precision'],0.9)

    def test_aggregate_runs_averages_numeric_metrics(self):
        from benchmark import aggregate_runs
        with tempfile.TemporaryDirectory() as tmp:
            a=self.make_run(Path(tmp)/'a'); b=self.make_run(Path(tmp)/'b',status='unverified_gaps')
            agg=aggregate_runs([a,b]); self.assertEqual(agg['runs'],2); self.assertEqual(agg['validated'],0.5); self.assertEqual(agg['citation_coverage'],1.0)

    def test_draco_rubric_metrics_present(self):
        from benchmark import score_run
        with tempfile.TemporaryDirectory() as tmp:
            d=self.make_run(tmp)
            # fact-check verdicts: one supported, one not_found → penalty applies
            (d/'claim_verification.json').write_text(json.dumps({
                'verdicts': 2, 'supported': 1, 'refuted': 1, 'not_found': 0,
                'numeric_precision': {'claims_with_numbers': 1, 'exact': 0, 'rate': 0.0},
            }))
            score=score_run(d)
            self.assertIn('rubric_factual_accuracy', score)
            self.assertIn('rubric_total', score)
            self.assertIn('rubric_negative_hallucination', score)
            # factual 0.5 - 0.35 (refuted) - 0.25 (numeric mismatch) = 0.0
            self.assertEqual(score['rubric_factual_accuracy'], 0.0)

    def test_draco_rubric_clean_run_high_score(self):
        from benchmark import score_run
        with tempfile.TemporaryDirectory() as tmp:
            d=self.make_run(tmp)
            (d/'claim_verification.json').write_text(json.dumps({
                'verdicts': 2, 'supported': 2, 'refuted': 0, 'not_found': 0,
                'numeric_precision': {'claims_with_numbers': 0, 'exact': 0, 'rate': None},
            }))
            score=score_run(d)
            self.assertEqual(score['rubric_factual_accuracy'], 1.0)
            self.assertGreater(score['rubric_total'], 0.7)

class EvalDatasetTests(unittest.TestCase):
    def test_dataset_contains_30_diverse_questions(self):
        path=ROOT/'evals'/'questions.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(data),30)
        self.assertEqual(len({item['id'] for item in data}),30)
        self.assertGreaterEqual(len({item['category'] for item in data}),7)
        for item in data:
            self.assertIn('prompt',item); self.assertIn('time_sensitivity',item); self.assertIn('expected_source_classes',item)
