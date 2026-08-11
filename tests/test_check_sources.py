import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))

class Handler(BaseHTTPRequestHandler):
    def _respond(self):
        path=self.path
        if path=='/ok': self.send_response(200)
        elif path=='/redirect': self.send_response(302); self.send_header('Location','/ok')
        elif path=='/restricted': self.send_response(403)
        elif path=='/dead': self.send_response(404)
        elif path=='/rate': self.send_response(429)
        elif path=='/server': self.send_response(503)
        else: self.send_response(410)
        self.end_headers()
    def do_HEAD(self): self._respond()
    def do_GET(self): self._respond()
    def log_message(self,*args): pass

class CheckSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler); cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close()
    def classify(self,path):
        from check_sources import classify_url
        return classify_url(f'http://127.0.0.1:{self.port}{path}',timeout=2)
    def test_http_classifications(self):
        expected={'/ok':'ok','/redirect':'ok','/restricted':'restricted','/dead':'dead','/rate':'rate_limited','/server':'transient_error'}
        for path,status in expected.items():
            with self.subTest(path=path): self.assertEqual(self.classify(path)['status'],status)
    def test_redirect_records_final_url(self):
        result=self.classify('/redirect'); self.assertTrue(result['final_url'].endswith('/ok')); self.assertEqual(result['http_code'],200)
