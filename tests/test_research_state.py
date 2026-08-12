import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class ResearchStateTests(unittest.TestCase):
    def setUp(self):
        from research_state import init_state, load_state, consume, remaining, rank_gaps, decide_next, BudgetExceeded
        self.init_state=init_state; self.load_state=load_state; self.consume=consume; self.remaining=remaining; self.rank_gaps=rank_gaps; self.decide_next=decide_next; self.BudgetExceeded=BudgetExceeded

    def test_budget_is_global_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'moderate')
            for _ in range(16): self.consume(path,'query')
            self.assertEqual(self.load_state(path)['budget']['query_calls'],16)
            with self.assertRaises(self.BudgetExceeded): self.consume(path,'query')
            self.assertEqual(self.remaining(path)['query'],0)

    def test_other_counters_are_not_reset_by_consumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'moderate')
            self.consume(path,'fetch',3); self.consume(path,'investigator',2); self.consume(path,'query',4)
            state=self.load_state(path)
            self.assertEqual(state['budget']['fetch_calls'],3); self.assertEqual(state['budget']['investigator_calls'],2); self.assertEqual(state['budget']['query_calls'],4)

    def test_gap_ranking_uses_importance_uncertainty_resolvability(self):
        ranked=self.rank_gaps([
            {'id':'G1','importance':1.0,'uncertainty':0.9,'resolvability':0.8},
            {'id':'G2','importance':0.5,'uncertainty':1.0,'resolvability':1.0},
        ])
        self.assertEqual(ranked[0]['id'],'G1'); self.assertAlmostEqual(ranked[0]['score'],0.72)

    def test_decide_synthesizes_when_value_is_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'moderate')
            decision=self.decide_next(path,[{'id':'G1','importance':0.2,'uncertainty':0.2,'resolvability':0.2}],threshold=0.25)
            self.assertEqual(decision['decision'],'SYNTHESIZE')

    def test_decide_continues_with_highest_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'moderate')
            decision=self.decide_next(path,[{'id':'G1','importance':'high','uncertainty':0.8,'resolvability':0.8},{'id':'G2','importance':'low','uncertainty':1,'resolvability':1}],threshold=0.25)
            self.assertEqual(decision['decision'],'CONTINUE'); self.assertEqual(decision['gap']['id'],'G1')

    def test_budget_exhaustion_forces_synthesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'surface')
            for _ in range(8): self.consume(path,'query')
            decision=self.decide_next(path,[{'id':'G1','importance':1,'uncertainty':1,'resolvability':1}])
            self.assertEqual(decision['decision'],'SYNTHESIZE'); self.assertEqual(decision['reason'],'budget_exhausted')

    def test_subtopic_saturated_when_sources_and_aspects_covered(self):
        from research_state import init_state, subtopic_saturated
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; state=self.init_state(path,'moderate')
            self.assertTrue(subtopic_saturated(state,'pricing',high_cred_sources=3,key_aspects_covered=2,key_aspects_total=2))
            self.assertFalse(subtopic_saturated(state,'pricing',high_cred_sources=2,key_aspects_covered=2,key_aspects_total=2))
            self.assertFalse(subtopic_saturated(state,'pricing',high_cred_sources=3,key_aspects_covered=1,key_aspects_total=2))

    def test_mark_saturated_persists(self):
        from research_state import init_state, mark_saturated, subtopic_saturated
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; state=self.init_state(path,'moderate')
            state=mark_saturated(state,'features')
            self.assertTrue(state['subtopic_saturation']['features']['saturated'])
            self.assertTrue(subtopic_saturated(state,'features',high_cred_sources=1,key_aspects_covered=0,key_aspects_total=1))

class ConcurrentResearchStateTests(ResearchStateTests):
    def test_concurrent_consumption_does_not_lose_updates(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; self.init_state(path,'moderate')
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda _: self.consume(path,'query'), range(16)))
            self.assertEqual(self.load_state(path)['budget']['query_calls'],16)
