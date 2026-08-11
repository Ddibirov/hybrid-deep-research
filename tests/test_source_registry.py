import json
import tempfile
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class SourceRegistryTests(unittest.TestCase):
    def setUp(self):
        from source_registry import init_registry, add_source, freeze_registry, load_registry
        self.init_registry=init_registry; self.add_source=add_source; self.freeze_registry=freeze_registry; self.load_registry=load_registry

    def test_add_assigns_stable_id_hashes_and_deduplicates_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source_registry.json'; self.init_registry(path)
            s1=self.add_source(path,title='A',url='https://Example.com/a/',source_type='official_docs',content='body',finding='finding')
            s2=self.add_source(path,title='A duplicate',url='https://example.com/a',source_type='official_docs',content='other',finding='other')
            self.assertEqual(s1['id'],'S1'); self.assertEqual(s2['id'],'S1')
            self.assertEqual(len(self.load_registry(path)['sources']),1)
            self.assertRegex(s1['content_sha256'],r'^[0-9a-f]{64}$'); self.assertRegex(s1['finding_sha256'],r'^[0-9a-f]{64}$')

    def test_freeze_prevents_mutation_and_records_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source_registry.json'; self.init_registry(path); self.add_source(path,title='A',url='https://example.com/a',source_type='official_docs')
            frozen=self.freeze_registry(path)
            self.assertTrue(frozen['frozen']); self.assertRegex(frozen['registry_sha256'],r'^[0-9a-f]{64}$')
            with self.assertRaises(RuntimeError): self.add_source(path,title='B',url='https://example.com/b',source_type='news')

    def test_atomic_write_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source_registry.json'; self.init_registry(path)
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])
            json.loads(path.read_text())

class ConcurrentSourceRegistryTests(SourceRegistryTests):
    def test_concurrent_adds_keep_unique_ids(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source_registry.json'; self.init_registry(path)
            def add(i): return self.add_source(path,title=f'S{i}',url=f'https://example.com/{i}',source_type='news')
            with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(add,range(10)))
            sources=self.load_registry(path)['sources']
            self.assertEqual(len(sources),10); self.assertEqual(len({s['id'] for s in sources}),10)
