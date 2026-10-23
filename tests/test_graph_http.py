"""HTTP security and reconnect tests against the real service and graph scheduler."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

import server
import ultra
from ultra_tools import Registry
from workflow_runtime import WorkflowService
from test_workflow_runtime import Model, NOTE, AVAILABLE, TIMEOUT_S


@unittest.skipUnless(AVAILABLE, 'Optional LangGraph dependencies not installed')
class GraphHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.settings=replace(ultra.Settings(),enabled=True)
        self.model=Model();self.model.delay=.2
        registry=Registry(lambda:self.settings,{'notes_search':lambda query:{'notes':[NOTE]},'note_read':lambda id:NOTE})
        self.service=WorkflowService(lambda:self.settings,registry,lambda:self.model,threading.BoundedSemaphore(1),
            'Use supplied data.',root=Path(self.tmp.name)/'runs')
        self.patch=patch.object(server,'WORKFLOWS',self.service);self.patch.start();self.addCleanup(self.patch.stop)
        self.http=server.GalaxyServer(('127.0.0.1',0),server.Handler)
        self.port=self.http.server_address[1];self.origin='http://127.0.0.1:'+str(self.port)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.service.close();self.http.shutdown();self.http.server_close()

    def call(self,path,body=None,origin=True,host=None,method=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=TIMEOUT_S)
        headers={'Host':host or '127.0.0.1:'+str(self.port)}
        if origin:headers['Origin']=self.origin if origin is True else origin
        if body is not None:headers['Content-Type']='application/json'
        c.request(method or ('POST' if body is not None else 'GET'),path,json.dumps(body) if body is not None else None,headers)
        r=c.getresponse();status=r.status;data=r.read();c.close();return status,data

    def test_origin_host_private_paths_and_bad_requests(self):
        for origin in (False,'https://outside.example'):
            self.assertEqual(self.call('/workflows/start',{'question':'test'},origin=origin)[0],403)
        self.assertEqual(self.call('/workflows',host='outside.example')[0],403)
        self.assertEqual(self.call('/workflows/start',[])[0],400)
        self.assertEqual(self.call('/workflows/start',{'question':'test','graph':'uploaded'})[0],400)
        self.assertEqual(self.call('/workflows/run?id=../../config.json')[0],404)
        self.assertEqual(self.call('/.local/graph-workflows/catalog.sqlite')[0],404)
        self.assertEqual(self.call('/workflows',method='HEAD')[0],200)
        self.assertEqual(self.call('/workflows',method='HEAD')[1],b'')

    def test_disconnect_reconnect_returns_complete_snapshot(self):
        status,body=self.call('/workflows/start',{'question':'Test budget','workflow':'research'})
        self.assertEqual(status,202);run=json.loads(body)
        def connect():
            c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=TIMEOUT_S)
            c.request('GET','/workflows/events?id='+run['id'],headers={'Last-Event-ID':'99999'})
            r=c.getresponse();self.assertEqual(r.status,200)
            self.assertEqual(r.getheader('Content-Type'),'text/event-stream')
            lines=[]
            while True:
                line=r.readline()
                if line==b'\n':break
                lines.append(line)
            state=json.loads(next(x[6:] for x in lines if x.startswith(b'data: ')))
            r.close();c.close();return state
        initial=connect();self.assertEqual(initial['id'],run['id'])
        self.service.thread.join(TIMEOUT_S)
        final=connect();self.assertEqual(final['status'],'complete');self.assertIsNotNone(final['result'])
        self.assertGreater(final['sequence'],initial['sequence'])
        self.assertEqual(len(self.model.calls),4)

    def test_cancel_via_http_and_conflict(self):
        self.model.delay=1
        _,body=self.call('/workflows/start',{'question':'Test budget'});run=json.loads(body)
        self.assertEqual(self.call('/workflows/start',{'question':'Another'})[0],429)
        self.assertEqual(self.call('/workflows/cancel',{'id':run['id']})[0],202)
        self.service.thread.join(TIMEOUT_S)
        self.assertEqual(self.service.detail(run['id'])['status'],'cancelled')
        self.assertEqual(self.call('/workflows/cancel',{'id':run['id']})[0],409)


if __name__=='__main__':unittest.main()
