import json,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class FinalizerTests(unittest.TestCase):
    def make_artifacts(self,tmp,claim_verification='supported',claim_confidence='high',draft_status='validated'):
        from source_registry import init_registry,add_source,freeze_registry
        from claim_ledger import init_ledger,add_claim,freeze_ledger
        tmp=Path(tmp); registry=tmp/'source_registry.json'; claims=tmp/'claims.jsonl'; report=tmp/'report.md'; manifest=tmp/'report_manifest.json'
        init_registry(registry); add_source(registry,title='Official',url='https://example.com/source',source_type='official_docs',content='content',finding='finding'); freeze_registry(registry)
        init_ledger(claims); add_claim(claims,claim='Version is 1.2.3',claim_class='release',importance='high',evidence=[{'source_id':'S1','support':'direct'}],confidence=claim_confidence,verification=claim_verification); freeze_ledger(claims)
        report.write_text(f'''---\nstatus: {draft_status}\ntopic: Example\nrounds: 1\nsources_count: 999\nsemantic_verification: passed\nstructural_validation: passed\n---\n# Example\n\n## Findings\nVersion is 1.2.3 [S1] <!-- claims:C1 -->\n\n## Sources\n[S1] Official — https://example.com/source\n''',encoding='utf-8')
        manifest.write_text(json.dumps({'status':'pending','topic':'Example','rounds':1}),encoding='utf-8')
        return report,manifest,registry,claims

    def test_finalizer_overrides_self_certification_and_validates(self):
        from finalize_report import finalize
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp,draft_status='validated')
            result=finalize(report,manifest,registry,claims,semantic_verification='passed')
            self.assertEqual(result['status'],'validated'); self.assertEqual(result['structural_validation'],'passed'); self.assertEqual(result['sources_count'],1); self.assertEqual(result['coverage'],'complete'); self.assertEqual(result['confidence'],'high')
            text=report.read_text(); self.assertIn('sources_count: 1',text); self.assertIn('status: validated',text)

    def test_semantic_failure_cannot_be_validated(self):
        from finalize_report import finalize
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp)
            result=finalize(report,manifest,registry,claims,semantic_verification='failed')
            self.assertEqual(result['status'],'unverified_gaps'); self.assertEqual(result['semantic_verification'],'failed')

    def test_partial_claim_coverage_is_unverified(self):
        from finalize_report import finalize
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp,claim_verification='unverified',claim_confidence='low')
            result=finalize(report,manifest,registry,claims,semantic_verification='passed')
            self.assertEqual(result['status'],'unverified_gaps'); self.assertEqual(result['coverage'],'partial'); self.assertEqual(result['confidence'],'low')

    def test_finalizer_requires_frozen_registry_and_ledger(self):
        from finalize_report import finalize
        from source_registry import load_registry
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp)
            data=load_registry(registry); data['frozen']=False; registry.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(RuntimeError): finalize(report,manifest,registry,claims,semantic_verification='passed')

class IntegrityFinalizerTests(FinalizerTests):
    def test_tampered_frozen_registry_is_rejected(self):
        from finalize_report import finalize
        from source_registry import load_registry
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp)
            data=load_registry(registry); data['sources'][0]['title']='tampered'; registry.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(RuntimeError): finalize(report,manifest,registry,claims,semantic_verification='passed')

    def test_tampered_frozen_claim_ledger_is_rejected(self):
        from finalize_report import finalize
        with tempfile.TemporaryDirectory() as tmp:
            report,manifest,registry,claims=self.make_artifacts(tmp)
            text=claims.read_text().replace('Version is 1.2.3','Version is 9.9.9'); claims.write_text(text)
            with self.assertRaises(RuntimeError): finalize(report,manifest,registry,claims,semantic_verification='passed')
