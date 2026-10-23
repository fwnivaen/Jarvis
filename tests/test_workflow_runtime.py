"""Real LangGraph/checkpoint tests with a deterministic model boundary (zero spending)."""
import json
import queue
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import ultra
from codex_bridge import BridgeError
from ultra_tools import Registry
from workflow_runtime import WorkflowService, WorkflowError, Redactor, RunStore

try:
    import langgraph.checkpoint.sqlite
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

TIMEOUT_S = 8
POLL_S = .01
NOTE = {'id': 1, 'title': 'Test budget', 'text': 'The budget is 100 dollars.', 'revision': 'test-revision'}


class Model:
    def __init__(self):
        self.calls = []
        self.active = self.peak = 0
        self.lock = threading.Lock()
        self.delay = .01
        self.failure = None
        self.failed = False
        self.tool = False
        self.closed = False

    def complete(self, **call):
        with self.lock:
            self.calls.append(call)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            until = time.monotonic() + self.delay
            while time.monotonic() < until:
                if call['cancel_event'].wait(POLL_S):
                    raise BridgeError('cancelled')
                if time.monotonic() >= call['deadline']:
                    raise BridgeError('timeout')
            if self.failure and not self.failed:
                self.failed = True
                raise BridgeError(self.failure)
            if self.tool and 'tool_handler' in call:
                call['tool_handler']('note_read', {'id': 1}, call['deadline'])
            call['observer']({'inputTokens': 10, 'outputTokens': 4, 'totalTokens': 14})
            value = {'answer': 'The budget is 100 dollars.', 'nodes': [1], 'about_notes': True,
                'evidence': [{'node': 1, 'quote': 'The budget is 100 dollars.'}], 'calculations': []}
            if 'unresolved_issues' in call['schema']['properties']:
                value['unresolved_issues'] = []
            return json.dumps(value)
        finally:
            with self.lock:
                self.active -= 1

    def close(self):
        self.closed = True


@unittest.skipUnless(AVAILABLE, 'Optional LangGraph dependencies not installed')
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = replace(ultra.Settings(), enabled=True, terminal_monitor_enabled=False)
        self.model = Model()
        self.notes = dict(NOTE)
        self.registry = Registry(lambda: self.settings, {
            'notes_search': lambda query: {'notes': [dict(self.notes)]},
            'note_read': lambda id: dict(self.notes)})
        self.slots = threading.BoundedSemaphore(1)
        self.service = self.make_service()
        self.addCleanup(lambda: self.service.close())

    def make_service(self):
        return WorkflowService(lambda: self.settings, self.registry, lambda: self.model,
            self.slots, 'Use supplied evidence.', root=Path(self.tmp.name)/'runs')

    def wait(self, service=None):
        service = service or self.service
        service.thread.join(TIMEOUT_S)
        self.assertFalse(service.thread.is_alive(), 'Workflow exceeded test bound')
        return service.catalog()['runs'][0]

    def test_real_graph_parallel_tools_outputs_and_persistence(self):
        self.model.tool = True
        self.service.start('Analyze the budget', 'research')
        run = self.wait()
        self.assertEqual(run['status'], 'complete', run)
        self.assertEqual(self.model.peak, 3)
        self.assertEqual(len(self.model.calls), 4)
        self.assertEqual(run['total_tokens'], 56)
        self.assertEqual(run['tool_calls'], 4)
        reviewer=self.model.calls[-1]
        self.assertEqual(len(reviewer['payload']['confirmed_tool_calls']),3)
        self.assertTrue(all(item['tool']=='note_read' for item in reviewer['payload']['confirmed_tool_calls']))
        self.assertIn('Earlier workflow phases have already executed',reviewer['system'])
        self.assertEqual(run['result']['nodes'], [1])
        self.assertTrue(any(e['kind']=='tool_complete' for e in run['events']))
        self.assertTrue(any(e.get('node')=='review' for e in run['events']))
        self.service.close(); self.service=self.make_service()
        saved=self.service.catalog()['runs'][0]
        self.assertEqual(saved['result'],run['result'])
        for p in (Path(self.tmp.name)/'runs').glob('*.sqlite'):
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_concurrency_is_bounded_and_shared_with_chat(self):
        self.model.delay = .15
        self.service.start('Analyze the budget')
        def launch(_):
            try:self.service.start('Another task')
            except WorkflowError as e:return e.status
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(launch,range(20))), [429]*20)
        self.assertFalse(self.slots.acquire(blocking=False))
        self.assertEqual(self.wait()['status'], 'complete')
        self.assertTrue(self.slots.acquire(blocking=False));self.slots.release()

    def test_cancel_stops_active_model_and_releases_capacity(self):
        self.model.delay=1
        run=self.service.start('Analyze the budget')
        end=time.monotonic()+TIMEOUT_S
        while not self.model.calls and time.monotonic()<end:time.sleep(POLL_S)
        start=time.monotonic();self.service.cancel(run['id']);run=self.wait()
        self.assertEqual(run['status'],'cancelled')
        self.assertLess(time.monotonic()-start,.5)
        self.assertEqual(self.model.active,0)
        self.assertIsNone(run['result'])

    def test_retry_preserves_completed_workers_and_original_budget(self):
        self.model.failure='tool_failed'
        run=self.service.start('Analyze the budget')
        failed=self.wait();self.assertEqual(failed['status'],'failed')
        before=len(self.model.calls);expires=self.service.store.get(run['id'])['expires_at']
        completed=sum(a['status']=='complete' for a in failed['agents'])
        self.assertGreater(completed,0)
        self.service.start(resume=run['id']);result=self.wait()
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(len(self.model.calls)-before,4-completed)
        self.assertEqual(self.service.store.get(run['id'])['expires_at'],expires)

    def test_reopen_recovers_interrupted_run(self):
        self.model.failure='tool_failed';run=self.service.start('Analyze the budget');self.wait()
        self.service.change(run['id'],status='running');self.service.close();self.service=self.make_service()
        self.assertEqual(self.service.catalog()['runs'][0]['status'],'interrupted')
        self.service.start(resume=run['id']);self.assertEqual(self.wait()['status'],'complete')

    def test_deadline_and_expired_retry(self):
        self.settings=replace(self.settings,worker_timeout_s=1,request_timeout_s=1)
        self.model.delay=2;run=self.service.start('Analyze the budget');result=self.wait()
        self.assertEqual(result['status'],'failed')
        self.assertFalse(result['can_retry'])
        with self.assertRaises(WorkflowError):self.service.start(resume=run['id'])
        self.assertTrue(self.slots.acquire(blocking=False));self.slots.release()

    def test_transport_retry_and_usage(self):
        self.model.failure='disconnected';self.service.start('Analyze the budget','general');run=self.wait()
        self.assertEqual(run['status'],'complete')
        self.assertEqual(len(self.model.calls),3)
        self.assertFalse(run['usage_complete'])
        self.assertEqual(run['agents'][0]['attempts'],2)

    def test_failed_tool_is_visible(self):
        self.registry.callbacks['notes_search']=lambda query: (_ for _ in ()).throw(ValueError('private detail'))
        self.service.start('Analyze the budget');run=self.wait()
        self.assertEqual(run['status'],'failed')
        self.assertEqual(run['error'],'tool_failed')
        self.assertNotIn('private detail',json.dumps(run))
        self.assertTrue(any(e['kind']=='tool_failed' for e in run['events']))

    def test_changed_source_blocks_resume(self):
        self.model.failure='tool_failed';run=self.service.start('Analyze the budget');self.wait()
        self.notes['revision']='changed';self.service.start(resume=run['id']);run=self.wait()
        self.assertEqual(run['error'],'source_changed')

    def test_redaction_and_no_raw_trace(self):
        self.service.redactor=Redactor(['a-configured-secret'])
        self.service.start('Analyze api_key=hidden-value and sk-1234567890 and a-configured-secret')
        run=self.wait();public=json.dumps(run)
        for secret in ['hidden-value','sk-1234567890','a-configured-secret']:
            self.assertNotIn(secret,public)
        for event in run['events']:
            self.assertFalse(set(event)&{'payload','arguments','reasoning','system','response'})

    def test_invalid_input_and_disabled_flags(self):
        for question in ['',[], 'a'*2001]:
            with self.assertRaises(WorkflowError):self.service.start(question)
        with self.assertRaises(WorkflowError):self.service.start('task','untrusted_graph')
        with self.assertRaises(WorkflowError):self.service.start('task',[])
        self.settings=replace(self.settings,enabled=False)
        with self.assertRaises(WorkflowError):self.service.start('task')

    def test_slow_read_tool_cancel_is_bounded(self):
        gate=threading.Event()
        self.addCleanup(gate.set)
        self.registry.callbacks['notes_search']=lambda query: (gate.wait(TIMEOUT_S), {'notes':[NOTE]})[1]
        run=self.service.start('Analyze the budget')
        time.sleep(.05)
        started=time.monotonic();self.service.cancel(run['id']);result=self.wait()
        self.assertEqual(result['status'],'cancelled')
        self.assertLess(time.monotonic()-started,.5)
        gate.set()

    def test_retry_never_replenishes_attempts(self):
        self.settings=replace(self.settings,worker_retries=0)
        self.model.failure='disconnected';run=self.service.start('Analyze the budget','general')
        result=self.wait();self.assertFalse(result['can_retry'])
        with self.assertRaises(WorkflowError):self.service.start(resume=run['id'])
        self.assertEqual(len(self.model.calls),1)

    def test_recovery_source_check_is_visible_and_cancellable(self):
        self.model.failure='tool_failed'
        run=self.service.start('Analyze the budget');self.wait()
        gate,entered=threading.Event(),threading.Event()
        self.addCleanup(gate.set)
        def slow_read(id):
            entered.set();gate.wait(TIMEOUT_S);return dict(NOTE)
        self.registry.callbacks['note_read']=slow_read
        calls_before=len(self.model.calls)
        self.service.start(resume=run['id'])
        self.assertTrue(entered.wait(TIMEOUT_S))
        started=time.monotonic();self.service.cancel(run['id']);result=self.wait()
        self.assertEqual(result['status'],'cancelled')
        self.assertLess(time.monotonic()-started,.5)
        self.assertEqual(len(self.model.calls),calls_before)
        self.assertTrue(any(e.get('slot')=='recovery' and e['kind']=='tool_started' for e in result['events']))
        gate.set()

    def test_known_secret_is_removed_from_outputs(self):
        self.service.redactor=Redactor(['100 dollars'])
        self.service.start('Analyze the budget','general')
        result=self.wait()
        self.assertNotIn('100 dollars',json.dumps(result))
        self.assertIn('[redacted]',result['result']['answer'])

    def test_checkpoint_not_readable_as_user_supplied_path(self):
        self.service.initialize()
        with self.assertRaises(WorkflowError):self.service.detail('../../config.json')
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        linked=Path(self.tmp.name)/'link';linked.symlink_to(outside)
        with self.assertRaises(OSError):RunStore(linked)


if __name__=='__main__':unittest.main()
