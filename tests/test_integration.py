import shutil,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class IntegrationTests(unittest.TestCase):
    def run_fixture(self,name,mutate=None):
        from finalize_report import finalize
        from verify_report import validate
        src=ROOT/'fixtures'/name
        with tempfile.TemporaryDirectory() as tmp:
            dst=Path(tmp)/name; shutil.copytree(src,dst)
            if mutate: mutate(dst)
            result=finalize(dst/'report.md',dst/'report_manifest.json',dst/'source_registry.json',dst/'claims.jsonl',semantic_verification='passed')
            errors=validate(dst/'report.md',dst/'source_registry.json',dst/'claims.jsonl')
            return result,errors

    def test_english_fixture_validates_end_to_end(self):
        result,errors=self.run_fixture('valid-en'); self.assertEqual(result['status'],'validated'); self.assertEqual(errors,[])

    def test_spanish_fixture_validates_end_to_end(self):
        result,errors=self.run_fixture('valid-es'); self.assertEqual(result['status'],'validated'); self.assertEqual(errors,[])

    def test_corrupted_source_url_is_rejected(self):
        def mutate(dst):
            p=dst/'report.md'; p.write_text(p.read_text().replace('https://example.com/source','https://example.com/invented'))
        result,errors=self.run_fixture('valid-en',mutate); self.assertEqual(result['status'],'unverified_gaps'); self.assertTrue(any('source URL mismatch' in e for e in errors))

    def test_uncited_table_data_row_is_rejected(self):
        def mutate(dst):
            p=dst/'report.md'; p.write_text(p.read_text().replace('1.2.3 [S1] <!-- claims:C1 -->','1.2.3 <!-- claims:C1 -->'))
        result,errors=self.run_fixture('valid-en',mutate); self.assertEqual(result['status'],'unverified_gaps'); self.assertTrue(any('table' in e and 'missing source citation' in e for e in errors))
