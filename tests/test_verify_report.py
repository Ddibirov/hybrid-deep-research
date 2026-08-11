import json,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from verify_report import validate
REGISTRY={'sources':[{'id':'S1','title':'Official source','url':'https://example.com/source','date':'2026-08-10','source_type':'official_docs'}]}
def report(*,count=1,citation='[S1]',source_id='S1',source_url='https://example.com/source',status='unverified_gaps',verification='passed',deterministic='pending'):
 return f'''---\nstatus: {status}\ntopic: Example\nrounds: 1\nsources_count: {count}\nverification: {verification}\ndeterministic_validation: {deterministic}\n---\n# Example\n\n## Key Findings\nThe stable release is version 1.2.3 {citation}\n\n## Sources\n[{source_id}] Official source — {source_url} (2026-08-10, official_docs; access: ok)\n'''
class ValidatorTests(unittest.TestCase):
 def run_validation(self, text, registry=REGISTRY):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp); rp=tmp/'report.md'; gp=tmp/'source_registry.json'; rp.write_text(text,encoding='utf-8'); gp.write_text(json.dumps(registry),encoding='utf-8'); return validate(rp,gp)
 def test_valid_report_passes(self): self.assertEqual(self.run_validation(report()),[])
 def test_uncited_paragraph_fails(self): self.assertTrue(any('uncited factual prose' in e for e in self.run_validation(report(citation=''))))
 def test_unknown_citation_fails(self): self.assertTrue(any('unknown citation IDs' in e for e in self.run_validation(report(citation='[S9]'))))
 def test_source_count_mismatch_fails(self): self.assertTrue(any('sources_count mismatch' in e for e in self.run_validation(report(count=18))))
 def test_invented_source_url_fails(self): self.assertTrue(any('source URL mismatch' in e for e in self.run_validation(report(source_url='https://example.com/invented'))))
 def test_raw_url_in_narrative_fails(self):
  text=report().replace('The stable release is version 1.2.3 [S1]','The stable release is at https://example.com/source and is version 1.2.3 [S1]'); self.assertTrue(any('raw URLs found outside Sources' in e for e in self.run_validation(text)))
 def test_confirmed_requires_validator_passed_metadata(self): self.assertTrue(any('status is confirmed' in e for e in self.run_validation(report(status='confirmed',deterministic='pending'))))
 def test_confirmed_requires_semantic_verification_passed(self): self.assertTrue(any('semantic verification' in e for e in self.run_validation(report(status='confirmed',verification='failed',deterministic='passed'))))
 def test_confirmed_with_passed_metadata_is_structurally_valid(self): self.assertEqual(self.run_validation(report(status='confirmed',deterministic='passed')),[])
if __name__=='__main__': unittest.main()

class V6ValidatorTests(ValidatorTests):
    CLAIMS = [
        {
            "id": "C1",
            "claim": "The stable release is version 1.2.3",
            "importance": "high",
            "evidence": [{"source_id": "S1", "support": "direct"}],
            "verification": "supported",
            "confidence": "high",
        }
    ]

    def run_v6(self, report_text, registry=REGISTRY, claims=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rp = tmp / "report.md"
            gp = tmp / "source_registry.json"
            cp = tmp / "claims.jsonl"
            rp.write_text(report_text, encoding="utf-8")
            gp.write_text(json.dumps(registry), encoding="utf-8")
            cp.write_text("\n".join(json.dumps(x) for x in (claims or self.CLAIMS)) + "\n", encoding="utf-8")
            return validate(rp, gp, cp)

    def v6_report(self, body, heading="Sources", source_sep="—"):
        return f"""---
status: pending
topic: Example
rounds: 1
sources_count: 1
semantic_verification: passed
structural_validation: pending
---
# Example

## Findings
{body}

## {heading}
[S1] Official source {source_sep} https://example.com/source
"""

    def test_uncited_list_item_fails(self):
        errors = self.run_v6(self.v6_report("- Stable release is 1.2.3 <!-- claims:C1 -->"))
        self.assertTrue(any("missing source citation" in e for e in errors), errors)

    def test_uncited_numbered_step_fails(self):
        errors = self.run_v6(self.v6_report("1. Install version 1.2.3 <!-- claims:C1 -->"))
        self.assertTrue(any("missing source citation" in e for e in errors), errors)

    def test_uncited_table_row_fails(self):
        body = "| Version | Date |\n|---|---|\n| 1.2.3 | 2026-08-10 | <!-- claims:C1 -->"
        errors = self.run_v6(self.v6_report(body))
        self.assertTrue(any("table" in e and "missing source citation" in e for e in errors), errors)

    def test_spanish_fuentes_heading_passes(self):
        text = self.v6_report("La versión estable es 1.2.3 [S1] <!-- claims:C1 -->", heading="Fuentes")
        self.assertEqual(self.run_v6(text), [])

    def test_source_separator_variants_pass(self):
        for sep in ("—", "–", "-"):
            with self.subTest(sep=sep):
                text = self.v6_report("Stable release is 1.2.3 [S1] <!-- claims:C1 -->", source_sep=sep)
                self.assertEqual(self.run_v6(text), [])

    def test_unknown_claim_id_fails(self):
        errors = self.run_v6(self.v6_report("Stable release is 1.2.3 [S1] <!-- claims:C9 -->"))
        self.assertTrue(any("unknown claim IDs" in e for e in errors), errors)

    def test_claim_source_mismatch_fails(self):
        claims = [{"id":"C1","claim":"x","importance":"high","evidence":[{"source_id":"S9","support":"direct"}],"verification":"supported","confidence":"high"}]
        errors = self.run_v6(self.v6_report("Stable release is 1.2.3 [S1] <!-- claims:C1 -->"), claims=claims)
        self.assertTrue(any("claim/source mismatch" in e for e in errors), errors)

    def test_list_item_with_claim_and_source_passes(self):
        text = self.v6_report("- Stable release is 1.2.3 [S1] <!-- claims:C1 -->")
        self.assertEqual(self.run_v6(text), [])
