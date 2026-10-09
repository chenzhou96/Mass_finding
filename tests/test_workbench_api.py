import http.client
import json
import threading
import time
import unittest
from unittest.mock import patch

from workbench.server import WorkbenchServer

P = dict(m2z=47.049141279571,error_pct=.0005,error_da=0,charge=1,
         ms_mode='ESI+',adduct_model=['H+'],elements={'C':2,'H':6,'O':1})


class WorkbenchAPITests(unittest.TestCase):
    def setUp(self):
        self.server=WorkbenchServer(('127.0.0.1',0))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def request(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
        default={'Origin':self.server.origin,'X-Workbench-Token':self.server.token,'Content-Type':'application/json'}
        conn.request('GET' if body is None else 'POST',path,body if isinstance(body,str) else json.dumps(body) if body is not None else None,headers=default if headers is None else headers)
        response=conn.getresponse();raw=response.read();status=response.status;headers=dict(response.getheaders());conn.close()
        return status,raw,headers

    def complete(self,job_id):
        for _ in range(100):
            state=json.loads(self.request('/api/jobs/'+job_id)[1])
            if state['status']!='running':return state
            time.sleep(.01)
        self.fail('Task did not complete')

    def test_config_and_static_assets_are_local_and_sandbox_policy_is_present(self):
        status,raw,headers=self.request('/api/config')
        self.assertEqual(status,200);self.assertEqual(json.loads(raw)['token'],self.server.token)
        for path in ('/','/app.js','/style.css'):
            status,raw,headers=self.request(path)
            self.assertEqual(status,200);self.assertIn("default-src 'self'",headers['Content-Security-Policy'])
            self.assertEqual(headers['Cache-Control'],'no-store')

    def test_known_mass_returns_shared_contract_without_cache_write(self):
        with patch('package.service.public.JSONExporter_formulaGeneration.export',side_effect=AssertionError('must not cache')):
            status,raw,_=self.request('/api/analyze',P)
            self.assertEqual(status,202)
            state=self.complete(json.loads(raw)['id'])
        self.assertEqual(state['status'],'success')
        self.assertEqual(state['result']['results'][0]['formula'],{'C':2,'O':1,'H':6})
        self.assertEqual(state['result']['metadata']['engine_version'],'2.0.0')

    def test_cross_origin_missing_token_and_dns_rebinding_host_are_denied(self):
        for headers in ({},{'Origin':'https://other.example','X-Workbench-Token':self.server.token},
                        {'Origin':self.server.origin,'X-Workbench-Token':self.server.token,'Host':'other.example'}):
            self.assertEqual(self.request('/api/analyze',P,headers)[0],403)
        self.assertEqual(self.request('/api/config',headers={'Host':'other.example'})[0],403)

    def test_traversal_and_unknown_endpoints_are_not_served(self):
        for path in ('/../run.py','/package/config/chem_element_config.json','/api/jobs/unknown'):
            self.assertEqual(self.request(path)[0],404)

    def test_nonfinite_invalid_unknown_and_oversized_inputs_fail_explicitly(self):
        for payload in ({**P,'charge':1.5},{**P,'error_pct':-1},{**P,'adduct_model':['unknown']},[],{'x':1}):
            self.assertEqual(self.request('/api/analyze',payload)[0],400)
        self.assertEqual(self.request('/api/analyze','{"m2z":NaN}')[0],400)
        self.assertEqual(self.request('/api/analyze','{}',{'Origin':self.server.origin,'X-Workbench-Token':self.server.token,'Content-Type':'application/json','Content-Length':'1000001'})[0],413)

    def test_duplicate_work_is_rejected_and_cancel_is_final(self):
        began=threading.Event()
        def slow(_payload,cancel_event):
            began.set();cancel_event.wait(3)
            return {'status':'success','results':[]}
        with patch('workbench.server.analyze',side_effect=slow):
            first=json.loads(self.request('/api/analyze',P)[1])['id'];self.assertTrue(began.wait(1))
            self.assertEqual(self.request('/api/analyze',P)[0],400)
            self.assertEqual(self.request('/api/cancel/'+first,{})[0],200)
            self.assertEqual(self.complete(first)['status'],'cancelled')
        self.assertNotIn('result',self.server.jobs[first])

    def test_cancel_already_completed_job_removes_success_before_first_poll(self):
        job_id=json.loads(self.request('/api/analyze',P)[1])['id']
        self.assertEqual(self.complete(job_id)['status'],'success')
        self.assertEqual(self.request('/api/cancel/'+job_id,{})[0],200)
        state=self.complete(job_id)
        self.assertEqual(state['status'],'cancelled')
        self.assertNotIn('result',state)

    def test_task_exception_is_visible_not_empty_success(self):
        with patch('workbench.server.analyze',side_effect=ValueError('synthetic limit')):
            job_id=json.loads(self.request('/api/analyze',P)[1])['id']
            state=self.complete(job_id)
        self.assertEqual(state['status'],'error');self.assertEqual(state['error'],'synthetic limit')

    def test_search_reuses_service_and_preserves_partial_status(self):
        result={'success':{'C2H6O':{'metadata':{'status':'partial'},'results':[]}},'partial':{'C2H6O':{'message':'missing synonyms'}}}
        with patch('package.service.formula_search_service.start_search',return_value=result) as search:
            status,raw,_=self.request('/api/search',{'formula':'C2H6O','ion_mode':'positive'})
            self.assertEqual(status,202);state=self.complete(json.loads(raw)['id'])
        self.assertEqual(state['result'],result);search.assert_called_once_with(['C2H6O'],'PubChem',ion_mode='positive')

    def test_search_formula_validation_prevents_unbounded_or_unknown_formula(self):
        for f in ('../data','C0','Xx2','C10001','<script>','',None):
            self.assertEqual(self.request('/api/search',{'formula':f})[0],400)

    def test_search_accepts_generated_unlimited_count_above_input_cap(self):
        # A finite input cap is limited to 1000; -1 can generate more atoms.
        with patch('package.service.formula_search_service.start_search', return_value={}) as search:
            status, raw, _ = self.request('/api/search', {'formula': 'H2000'})
            self.assertEqual(status, 202)
            self.assertEqual(self.complete(json.loads(raw)['id'])['status'], 'success')
        search.assert_called_once_with(['H2000'], 'PubChem', ion_mode='both')

    def test_binding_public_interfaces_is_prohibited(self):
        with self.assertRaises(ValueError):WorkbenchServer(('0.0.0.0',0))


if __name__=='__main__':unittest.main()
