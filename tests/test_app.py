"""Run: python -m unittest discover -s tests -v. No external dependencies."""
import io
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server as app

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=app.DB_PATH;app.DB_PATH=Path(self.temp.name)/'test.sqlite3';app.init_db()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.ws=self.post('/api/workspaces',{'name':'Test workspace'})['id']
        self.bid=self.get('/api/workspaces/'+self.ws)['branches'][0]['id']
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        app.DB_PATH=self.old_db
        # sqlite connections may be finalized after leaving transaction contexts.
        import gc;gc.collect()
        self.temp.cleanup()
    def request(self,path,data=None,headers=None,raw=False):
        h={'Content-Type':'application/json','X-Bloom-Token':app.TOKEN};h.update(headers or {})
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        with urllib.request.urlopen(req) as r:
            body=r.read().decode();return body if raw else json.loads(body)
    def get(self,p):return self.request(p)
    def post(self,p,d,**kw):return self.request(p,d,**kw)
    def note(self,text,bid=None):return self.post('/api/note',{'id':bid or self.bid,'content':text})['id']
    def fork(self,node,name='Side branch'):return self.post('/api/fork',{'node_id':node,'name':name})['id']
    def texts(self,bid):return [x['content'] for x in self.get('/api/branches/'+bid)['messages']]
    def test_nested_and_sibling_isolation(self):
        root=self.note('Shared root');a=self.fork(root,'A');b=self.fork(root,'B');c=self.fork(root,'C')
        self.note('Main only');self.note('A only',a);self.note('B only',b);self.note('C only',c)
        nested=self.fork(self.get('/api/branches/'+a)['branch']['head_id'],'Nested');self.note('Nested only',nested)
        self.assertEqual(self.texts(self.bid),['Shared root','Main only'])
        self.assertEqual(self.texts(b),['Shared root','B only'])
        self.assertEqual(self.texts(c),['Shared root','C only'])
        self.assertEqual(self.texts(nested),['Shared root','A only','Nested only'])
    def test_root_edit_is_immutable(self):
        root=self.note('Original');edited=self.post('/api/edit',{'node_id':root,'name':'Edit','content':'Replacement'})['id']
        self.assertEqual(self.texts(self.bid),['Original']);self.assertEqual(self.texts(edited),['Replacement'])
    def test_merge_excludes_shared_ancestors(self):
        root=self.note('Shared');side=self.fork(root);self.note('Unique idea',side)
        self.post('/api/merge',{'id':self.bid,'source_id':side})
        merged=self.texts(self.bid)[-1];self.assertIn('Unique idea',merged);self.assertNotIn('User: Shared',merged)
        self.assertEqual(self.texts(side),['Shared','Unique idea'])
    def test_cross_workspace_merge_rejected(self):
        other=self.post('/api/workspaces',{'name':'Other'})['id'];b=self.get('/api/workspaces/'+other)['branches'][0]['id']
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.post('/api/merge',{'id':self.bid,'source_id':b})
        self.assertEqual(ctx.exception.code,400)
    def test_archive_last_branch_rejected_and_restore(self):
        with self.assertRaises(urllib.error.HTTPError):self.post('/api/branch/update',{'id':self.bid,'archived':True})
        side=self.fork(self.note('Root'));self.post('/api/branch/update',{'id':side,'archived':True})
        self.assertEqual(self.get('/api/branches/'+side)['branch']['archived'],1)
        self.post('/api/branch/update',{'id':side,'archived':False});self.assertEqual(self.get('/api/branches/'+side)['branch']['archived'],0)
    def test_snapshot_restores_separate_copy(self):
        self.note('Before');snap=self.post('/api/snapshot',{'id':self.ws})['id'];self.note('After')
        copied=self.post('/api/snapshot/restore',{'id':snap})['id'];data=self.get('/api/workspaces/'+copied)
        self.assertNotEqual(copied,self.ws);self.assertEqual([m['content'] for m in data['messages']],['Before']);self.assertEqual(self.texts(self.bid),['Before','After'])
    def test_export_import_and_cycle_validation(self):
        self.note('Hello');data=self.get('/api/workspaces/'+self.ws)
        imported=self.post('/api/import',{'workspace':data})['id'];self.assertEqual(len(self.get('/api/workspaces/'+imported)['messages']),1)
        data['messages'][0]['parent_id']=data['messages'][0]['id']
        before=len(self.get('/api/bootstrap')['workspaces'])
        with self.assertRaises(urllib.error.HTTPError):self.post('/api/import',{'workspace':data})
        self.assertEqual(len(self.get('/api/bootstrap')['workspaces']),before)
    def test_csrf_and_host_protection(self):
        for headers in [{'X-Bloom-Token':'bad'},{'Origin':'https://evil.example'},{'Host':'evil.example'}]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.post('/api/note',{'id':self.bid,'content':'No'},headers=headers)
            self.assertEqual(ctx.exception.code,403)
        self.assertEqual(self.texts(self.bid),[])
    def test_streamed_reply_and_provider_context(self):
        root=self.note('Shared');side=self.fork(root);self.note('Sibling secret',side)
        payloads=[]
        def fake(path,payload=None,**kwargs):
            payloads.append(payload)
            return io.BytesIO(b'{"message":{"content":"Hello "},"done":false}\n{"message":{"content":"world"},"done":true}\n')
        with patch.object(app,'models',return_value={'connected':True,'models':['test-local']}),patch.object(app,'ollama',side_effect=fake):
            events=self.post('/api/chat',{'id':self.bid,'content':'Question','model':'test-local'},raw=True)
        self.assertIn('"type": "done"',events);self.assertEqual(self.texts(self.bid)[-1],'Hello world')
        self.assertNotIn('Sibling secret',json.dumps(payloads));self.assertNotIn(self.bid,app.BUSY)
    def test_failed_stream_saves_prompt_and_allows_retry(self):
        with patch.object(app,'models',return_value={'connected':True,'models':['test-local']}),patch.object(app,'ollama',side_effect=OSError('Offline')):
            events=self.post('/api/chat',{'id':self.bid,'content':'Keep this prompt','model':'test-local'},raw=True)
        self.assertIn('"type": "error"',events);self.assertEqual(self.texts(self.bid),['Keep this prompt']);self.assertNotIn(self.bid,app.BUSY)
        with patch.object(app,'models',return_value={'connected':True,'models':['test-local']}),patch.object(app,'ollama',return_value=io.BytesIO(b'{"message":{"content":"Recovered"},"done":true}\n')):
            self.post('/api/chat',{'id':self.bid,'content':'','model':'test-local'},raw=True)
        self.assertEqual(self.texts(self.bid),['Keep this prompt','Recovered'])
    def test_context_trims_without_deleting_history(self):
        for i in range(12):self.note(str(i)+' '+('x'*1000))
        with app.connect() as db:
            b=app.require(db,'branches',self.bid)
            context,notice,total=app.prepare_context(db,b,'test',limit=4096,summarize=False)
        self.assertLess(len(context),13);self.assertIn('omitted',notice);self.assertEqual(len(self.texts(self.bid)),12)
    def test_summary_is_cached_and_original_messages_preserved(self):
        for i in range(12):self.note(str(i)+' '+('x'*800))
        with patch.object(app,'ollama',return_value=io.BytesIO(b'{"message":{"content":"Earlier decisions preserved."}}')) as provider:
            with app.connect() as db:
                b=app.require(db,'branches',self.bid)
                first,notice,_=app.prepare_context(db,b,'test',limit=4096)
                second,_,_=app.prepare_context(db,b,'test',limit=4096)
            self.assertEqual(provider.call_count,1)
        self.assertEqual(first,second);self.assertIn('summarized',notice);self.assertIn('Earlier decisions preserved',first[0]['content']);self.assertEqual(len(self.texts(self.bid)),12)
    def test_import_preserves_merge_provenance(self):
        root=self.note('Root');side=self.fork(root);self.note('Insight',side)
        self.post('/api/merge',{'id':self.bid,'source_id':side})
        original=self.get('/api/workspaces/'+self.ws)
        wid=self.post('/api/import',{'workspace':original})['id'];copied=self.get('/api/workspaces/'+wid)
        self.assertEqual(len(copied['merges']),1)
        self.assertIn(copied['merges'][0]['message_id'],[m['id'] for m in copied['messages']])
    def test_persistence_and_500_message_performance(self):
        with app.connect() as db:
            b=app.require(db,'branches',self.bid)
            for i in range(500):app.append(db,b,'user',f'Message {i}')
        start=time.perf_counter();data=self.get('/api/workspaces/'+self.ws);path=self.get('/api/branches/'+self.bid)
        elapsed=time.perf_counter()-start
        self.assertEqual(len(data['messages']),500);self.assertEqual(len(path['messages']),500);self.assertLess(elapsed,2)

if __name__=='__main__':unittest.main()
