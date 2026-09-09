import importlib.util
import unittest
from test_rules import fixture


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'),'FastAPI/httpx saknas: API-tester är INTE körda')
class API(unittest.TestCase):
    def test_validate_endpoint(self):
        from fastapi.testclient import TestClient
        from bb.api import app
        d,s=fixture();r=TestClient(app).post('/api/validate',json=dict(data=d,schedule=s));self.assertEqual(r.status_code,200);self.assertTrue(r.json()['valid'])
    def test_bad_data_rejected(self):
        from fastapi.testclient import TestClient
        from bb.api import app
        r=TestClient(app).post('/api/optimize',json=dict(data={}));self.assertEqual(r.status_code,422)
