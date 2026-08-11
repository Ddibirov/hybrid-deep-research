import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class ClaimLedgerTests(unittest.TestCase):
    def setUp(self):
        from claim_ledger import init_ledger, add_claim, freeze_ledger, load_ledger
        self.init_ledger=init_ledger; self.add_claim=add_claim; self.freeze_ledger=freeze_ledger; self.load_ledger=load_ledger

    def test_claims_get_stable_ids_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claims.jsonl'; self.init_ledger(path)
            c1=self.add_claim(path,claim='Version is 1.2.3',claim_class='release',importance='high',evidence=[{'source_id':'S1','support':'direct','excerpt':'v1.2.3'}],confidence='high',verification='supported')
            self.assertEqual(c1['id'],'C1'); self.assertEqual(self.load_ledger(path)['claims'][0]['evidence'][0]['source_id'],'S1')

    def test_freeze_prevents_new_claims_and_records_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claims.jsonl'; self.init_ledger(path); self.add_claim(path,claim='x',claim_class='general',importance='medium',evidence=[],confidence='medium',verification='unverified')
            frozen=self.freeze_ledger(path)
            self.assertTrue(frozen['meta']['frozen']); self.assertRegex(frozen['meta']['ledger_sha256'],r'^[0-9a-f]{64}$')
            with self.assertRaises(RuntimeError): self.add_claim(path,claim='y',claim_class='general',importance='low',evidence=[],confidence='low',verification='unverified')

class ConcurrentClaimLedgerTests(ClaimLedgerTests):
    def test_concurrent_adds_keep_unique_ids(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claims.jsonl'; self.init_ledger(path)
            def add(i): return self.add_claim(path,claim=f'c{i}',claim_class='general',importance='low',evidence=[],confidence='low',verification='unverified')
            with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(add,range(10)))
            claims=self.load_ledger(path)['claims']
            self.assertEqual(len(claims),10); self.assertEqual(len({c['id'] for c in claims}),10)

class ClaimUpdateTests(ClaimLedgerTests):
    def test_update_claim_before_freeze(self):
        from claim_ledger import update_claim
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claims.jsonl'; self.init_ledger(path); c=self.add_claim(path,claim='x',claim_class='general',importance='high',evidence=[],confidence='low',verification='unverified')
            updated=update_claim(path,c['id'],verification='supported',confidence='high')
            self.assertEqual(updated['verification'],'supported'); self.assertEqual(updated['confidence'],'high')
    def test_update_claim_after_freeze_is_rejected(self):
        from claim_ledger import update_claim
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'claims.jsonl'; self.init_ledger(path); c=self.add_claim(path,claim='x',claim_class='general',importance='high',evidence=[],confidence='low',verification='unverified'); self.freeze_ledger(path)
            with self.assertRaises(RuntimeError): update_claim(path,c['id'],verification='supported')
