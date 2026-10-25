"""Boundary compatibility fixtures, kept separate from live acceptance evidence."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import note_store
import server
import ultra
from ultra_tools import Registry,ToolSession
from workflow_runtime import WorkflowService,WorkflowError
from test_workflow_runtime import AVAILABLE,Model,NOTE
from test_offline import request
from execution_control import digest
from learning_gate import LearningStore
from outcome_collection import capture,capture_execution
from tools.backup_execution import snapshot,restore

WAIT_S=8
POLL_S=.01


@unittest.skipUnless(AVAILABLE,'Optional LangGraph runtime unavailable')
class WorkflowCompatibility(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.settings=replace(ultra.Settings(),enabled=True,terminal_monitor_enabled=False)
        self.note=dict(NOTE,stable_id=digest('stable fixture'))
        self.model=Model()
        self.registry=Registry(lambda:self.settings,{'notes_search':lambda query:{'notes':[self.note]},'note_read':lambda id:self.note})
        self.service=WorkflowService(lambda:self.settings,self.registry,lambda:self.model,threading.BoundedSemaphore(1),
            'Read approved evidence.',root=Path(self.tmp.name)/'runs')
        self.addCleanup(self.service.close)
        self.service.source_resolver=lambda stable:{'id':9,'revision':self.note['revision']}

    def test_source_remap_is_stable_and_changed_content_is_historical(self):
        run=self.service.start('Synthetic','general');self.service.thread.join(WAIT_S)
        result=self.service.detail(run['id'])['result']
        self.assertEqual(result['nodes'],[9]);self.assertFalse(result['sources_changed'])
        self.note['revision']='changed'
        result=self.service.detail(run['id'])['result']
        self.assertEqual(result['nodes'],[]);self.assertTrue(result['sources_changed'])
        self.assertTrue(result['answer'])

    def test_admission_replay_cannot_start_another_task_even_after_completion(self):
        key='b'*24
        run=self.service.start('Synthetic','general',request_key=key)
        self.assertEqual(self.service.start('Synthetic','general',request_key=key)['id'],run['id'])
        with self.assertRaises(WorkflowError):self.service.start('Changed','general',request_key=key)
        self.service.thread.join(WAIT_S)
        calls=len(self.model.calls)
        self.assertEqual(self.service.start('Synthetic','general',request_key=key)['id'],run['id'])
        self.assertEqual(len(self.model.calls),calls)

    def test_cancelled_read_stays_cleanup_pending_until_callback_settles(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        self.registry.callbacks['notes_search']=lambda query:(entered.set(),release.wait(WAIT_S),{'notes':[self.note]})[-1]
        run=self.service.start('Synthetic','general');self.assertTrue(entered.wait(WAIT_S))
        self.service.cancel(run['id']);self.service.thread.join(WAIT_S)
        result=self.service.detail(run['id']);self.assertEqual(result['status'],'cancelled')
        self.assertEqual(result['cleanup'],'pending');self.assertFalse(result['can_retry'])
        self.assertEqual(self.service.active,run['id'])
        with self.assertRaises(WorkflowError):self.service.start('Must wait','general')
        release.set();end=time.monotonic()+WAIT_S
        while self.service.detail(run['id'])['cleanup']=='pending' and time.monotonic()<end:time.sleep(POLL_S)
        self.assertEqual(self.service.detail(run['id'])['cleanup'],'complete')
        self.assertIsNone(self.service.active)


class DataCompatibility(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_stable_note_http_survives_numeric_rebuild(self):
        (self.root/'synthetic.md').write_text('Synthetic evidence.')
        node={'id':9,'_path':'synthetic.md','group':'fixture'}
        expected=note_store.stable_id('synthetic.md')
        with patch.object(server,'NOTES',[node]),patch.object(server.build,'NOTES_DIR',self.root):
            status,_,raw=request('/note?stable='+expected)
            self.assertEqual(status,200);value=json.loads(raw)
            self.assertEqual(value['id'],9);self.assertEqual(value['stable_id'],expected)
            self.assertEqual(request('/note?stable='+digest('missing'))[0],404)

    def test_http_operation_session_deduplicates_replays(self):
        import functools
        writes=[]
        registry=Registry(lambda:replace(ultra.Settings(),enabled=True),{'notes_capture':lambda text:writes.append(text) or {'saved':True}})
        body={'name':'notes_capture','arguments':{'text':'synthetic'},'operation_session':'a'*24}
        with patch.object(server,'TOOLS',registry),patch.object(server.ultra_tools,'ToolSession',functools.partial(ToolSession,root=self.root)):
            for _ in range(2):self.assertEqual(request('/tools/call','POST',body,headers={'Origin':'http://127.0.0.1:4700'})[0],200)
            changed=dict(body,arguments={'text':'changed under the same key'})
            self.assertEqual(request('/tools/call','POST',changed,headers={'Origin':'http://127.0.0.1:4700'})[0],400)
        self.assertEqual(writes,['synthetic'])

    def test_opt_in_collector_stores_only_minimized_fields_and_unknown_cost(self):
        flags=self.root/'flags.json';storepath=self.root/'learning.sqlite'
        run={'id':'synthetic','status':'complete','created_at':100,'ended_at':101,'agents':{},
            'question':'private prompt must not persist','result':{'answer':'private answer must not persist'}}
        self.assertEqual(capture(run,flags_path=flags,store_path=storepath),'off');self.assertFalse(storepath.exists())
        flags.write_text(json.dumps({'outcome_collection':True}))
        self.assertEqual(capture(run,flags_path=flags,store_path=storepath),'stored')
        learning=LearningStore(storepath)
        try:record=json.loads(learning.db.execute('SELECT data FROM outcomes').fetchone()[0])
        finally:learning.close()
        self.assertIsNone(record['cost_microunits']);self.assertFalse(record['usage_complete'])
        self.assertNotIn('private',json.dumps(record))

    def test_real_sqlite_backup_restore_and_checksum_rejection(self):
        import sqlite3
        source=self.root/'source.sqlite'
        with sqlite3.connect(source) as db:db.execute('CREATE TABLE example(value TEXT)');db.execute('INSERT INTO example VALUES (?)',('synthetic',))
        backup=self.root/'backup';snapshot([source],backup)
        restored=self.root/'restored';restore(backup,restored)
        with sqlite3.connect(next(restored.glob('*.sqlite'))) as db:self.assertEqual(db.execute('SELECT value FROM example').fetchone()[0],'synthetic')
        next(backup.glob('*.sqlite')).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):restore(backup,self.root/'invalid')

    def test_both_executor_outcomes_use_scoped_minimized_scheduler_hook(self):
        flags=self.root/'flags.json';flags.write_text(json.dumps({'outcome_collection':True}))
        path=self.root/'learning.sqlite'
        for engine in ('langgraph','deepagents'):
            run={'id':engine,'status':'complete','project_id':'synthetic-project','conversation_id':'synthetic-conversation',
                'created_at':100,'ended_at':102,'versions':{'engine':engine,'model':'fixture','tools':'v1','behavior':'research-v1'}}
            status={'result':{'answer':'private answer'},'total_tokens':40,'usage_complete':True,'settled':True}
            self.assertEqual(capture_execution(run,status,flags_path=flags,store_path=path),'stored')
        store=LearningStore(path)
        try:
            rows=store.db.execute('SELECT scope,data FROM outcomes').fetchall()
            self.assertEqual(len(rows),2);self.assertNotIn('private answer',str(rows))
            self.assertNotIn('synthetic-project',str(rows))
            self.assertTrue(all(json.loads(data)['cost_microunits'] is None for _,data in rows))
        finally:store.close()


if __name__=='__main__':unittest.main()
