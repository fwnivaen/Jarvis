"""Real installed SDK + scripted model. These are not live provider comparisons."""
from pathlib import Path
import tempfile
import time
import threading
import unittest
from dataclasses import replace

from execution_adapters import DeepAgentsAdapter
from execution_control import ControlStore,ControlError
from execution_gateway import ToolGateway
from helper_protocol import frame,parse
from ultra_tools import Registry
import ultra

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'.local/deepagents-venv/bin/python'
NOTE={'id':1,'title':'Synthetic','text':'The synthetic budget is 100 dollars.','revision':'synthetic-v1'}


class ProtocolTests(unittest.TestCase):
    def test_auth_sequence_and_tampering(self):
        line=frame('synthetic-key',1,'step',{})
        self.assertEqual(parse('synthetic-key',1,line)['kind'],'step')
        for key,seq,raw in [('wrong',1,line),('synthetic-key',2,line),('synthetic-key',1,line.replace('step','tool'))]:
            with self.assertRaises(ValueError):parse(key,seq,raw)


@unittest.skipUnless(PYTHON.exists(),'Optional pinned SDK helper environment unavailable')
class SDKTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ControlStore(Path(self.tmp.name)/'control.sqlite');self.addCleanup(self.store.close)
        self.calls=[]
        def search(query):self.calls.append('notes_search');return {'notes':[NOTE]}
        def read(id):self.calls.append('note_read');return NOTE
        self.registry=Registry(lambda:replace(ultra.Settings(),enabled=True),{'notes_search':search,'note_read':read})
        self.run,_=self.store.admit('request',conversation_id='synthetic',project_id='test',engine='deepagents',
            versions={'engine':'deepagents==0.7.32','model':'fixture','tools':'fixture-v1','behavior':'research-v1'},
            permissions={'notes_search','note_read'},duration_s=30)
        self.store.transition(self.run['id'],'running')
        self.token=self.store.issue(self.run['id'])
        self.adapter=DeepAgentsAdapter(PYTHON,ToolGateway(self.store,self.registry),self.store,self.run['id'],self.token,
            lambda result:ultra.checked(result,[NOTE]))
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.adapter.process and not self.adapter.settled.is_set():
            self.adapter.cancel();self.adapter.settled.wait(5)

    def run_fixture(self,scenario='research'):
        self.adapter.start('Analyze the synthetic budget',fixture=True,scenario=scenario,duration_s=20)
        self.assertTrue(self.adapter.settled.wait(22),'SDK helper exceeded its bound')
        return self.adapter.status()

    def test_sdk_graph_real_tools_scratch_context_and_usage(self):
        status=self.run_fixture()
        self.assertEqual(status['status'],'complete',status)
        self.assertEqual(self.calls,['notes_search','note_read'])
        self.assertEqual(status['result']['nodes'],[1])
        self.assertGreater(sum(e['data']['total_tokens'] for e in self.adapter.events() if e['kind']=='usage'),0)
        self.assertIsNotNone(self.adapter.process.poll())
        self.assertFalse(status['capabilities']['resume'])
        with self.assertRaises(ControlError):self.adapter.resume()

    def test_bounded_compiled_child_uses_same_gateway(self):
        status=self.run_fixture('delegation')
        self.assertEqual(status['status'],'complete',status)
        self.assertEqual(self.calls,['note_read'])

    def test_undeclared_shell_is_blocked(self):
        status=self.run_fixture('forbidden')
        self.assertEqual(status['status'],'failed',status)
        self.assertIsNone(status['result'])

    def test_cancellation_confirms_subprocess_exit(self):
        self.adapter.start('Synthetic slow work',fixture=True,scenario='slow',duration_s=20)
        end=time.monotonic()+5
        while not self.adapter.events() and time.monotonic()<end:time.sleep(.02)
        start=time.monotonic();self.adapter.cancel()
        self.assertTrue(self.adapter.settled.wait(5))
        self.assertLess(time.monotonic()-start,3)
        self.assertEqual(self.adapter.state,'cancelled')
        self.assertIsNotNone(self.adapter.process.poll())
        with self.assertRaises(ControlError):self.store.authenticate(self.token,self.run['id'])

    def test_separate_credentials_required_without_changing_codex(self):
        from unittest.mock import patch
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(ControlError,'Separate authorized'):
                self.adapter.start('Research',model='fixture')
        self.assertIsNone(self.adapter.process)

    def test_cancel_kills_helper_but_retains_owner_while_read_callback_settles(self):
        entered,release=threading.Event(),threading.Event();self.addCleanup(release.set)
        self.registry.callbacks['notes_search']=lambda query:(entered.set(),release.wait(8),{'notes':[NOTE]})[-1]
        self.adapter.start('Synthetic',fixture=True,duration_s=20)
        self.assertTrue(entered.wait(5));self.adapter.cancel()
        end=time.monotonic()+5
        while self.adapter.process.poll() is None and time.monotonic()<end:time.sleep(.02)
        self.assertIsNotNone(self.adapter.process.poll())
        self.assertFalse(self.adapter.status()['settled'])
        release.set();self.assertTrue(self.adapter.settled.wait(3))
        self.assertEqual(self.adapter.status()['status'],'cancelled')


if __name__=='__main__':unittest.main()
