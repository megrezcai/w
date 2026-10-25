import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from caseforge.server import App, make_server
from caseforge.llm import Ollama, ModelError

ROOT=Path(__file__).resolve().parents[1]
class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=App(ROOT,self.tmp.name,demo=True)
        self.server=make_server(self.app,port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,data=None,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Caseforge-Token']=self.app.token
        req=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        with self.client.open(req) as r:return json.load(r)
    def test_auth_required(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/api/chapters',token=False)
        self.assertEqual(cm.exception.code,403)
    def test_persistence_and_player_export(self):
        s=self.request('/api/sessions',{'chapter_id':'rain_manor','character_id':'butler'})
        path='/api/sessions/'+s['session_id']
        out=self.request(path+'/turn',{'text':'厨房里的你怎么解释','evidence_ids':['camera']})
        self.assertEqual(out['strategy'],'disclose')
        restored=self.request(path)
        self.assertEqual(restored['turn'],1)
        exported=self.request(path+'/export')
        self.assertNotIn('工具箱',json.dumps(exported,ensure_ascii=False))
        reloaded=App(ROOT,self.tmp.name,demo=True)
        _,state,_=reloaded.read(s['session_id'])
        self.assertEqual(state['disclosed'],['corridor'])
    def test_snapshot_survives_chapter_changes(self):
        s=self.request('/api/sessions',{'chapter_id':'rain_manor','character_id':'butler'})
        original=self.app.chapters()['rain_manor']
        original['characters'][0]['secrets'][0]['truth']='改写后的真相'
        self.request('/api/chapters',{'chapter':original})
        out=self.request('/api/sessions/'+s['session_id']+'/turn',{'text':'厨房','evidence_ids':['camera']})
        self.assertNotIn('改写后的真相',out['reply'])
    def test_unknown_evidence_is_400(self):
        s=self.request('/api/sessions',{'chapter_id':'rain_manor','character_id':'butler'})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/api/sessions/'+s['session_id']+'/turn',{'text':'厨房','evidence_ids':['fake']})
        self.assertEqual(cm.exception.code,400)
    def test_demo_import_not_faked(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/api/compile',{'text':'剧本素材'*20})
        self.assertEqual(cm.exception.code,400)
    def test_json_chapter_validates(self):
        self.assertEqual(len(self.request('/api/chapters')),1)
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/chapters',{'chapter':{'version':1}})
    def test_llm_loopback_only(self):
        with self.assertRaises(ValueError):Ollama('https://example.com')
        with self.assertRaises(ValueError):Ollama('http://127.0.0.1/other')

class OllamaProtocolTests(unittest.TestCase):
    def test_local_chat_protocol(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(body)
                content=json.dumps({'message':{'content':'{"line":"收到"}'}},ensure_ascii=False).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=Ollama(f'http://127.0.0.1:{server.server_port}').complete('test',{'input':'hi'},{'type':'object'})
            self.assertEqual(result,{'line':'收到'})
            self.assertFalse(calls[0]['think']);self.assertFalse(calls[0]['stream'])
            self.assertIn('format',calls[0])
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
