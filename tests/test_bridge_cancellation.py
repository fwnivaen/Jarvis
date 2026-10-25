"""Verify transport cancellation interrupts the actual turn protocol boundary."""
import threading
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from codex_bridge import CodexBridge, BridgeError

MODEL='gpt-6-luna'


class CancellationTests(unittest.TestCase):
    def test_interrupt_ack_requires_terminal_event_or_process_termination(self):
        for confirmed in (False,True):
            with self.subTest(confirmed=confirmed):
                bridge=CodexBridge(None)
                bridge._scratch=SimpleNamespace(name='synthetic')
                bridge._process=SimpleNamespace()
                bridge._models={MODEL:{'supportedReasoningEfforts':[{'reasoningEffort':'high'}]}}
                cancelled=threading.Event()
                def rpc(method,params,deadline):
                    if method=='account/read':return {'account':{'type':'chatgpt'}}
                    if method=='account/rateLimits/read':return {'ordinaryUsageAllowed':True,'rateLimits':{'primary':{'usedPercent':0}}}
                    if method=='thread/start':return {'thread':{'id':'test-thread'}}
                    if method=='turn/start':cancelled.set();return {'turn':{'id':'test-turn'}}
                    if method=='turn/interrupt' and confirmed:bridge._calls['test-thread'].put(('done','interrupted'))
                    return {}
                with patch.object(bridge,'start'),patch.object(bridge,'_rpc',side_effect=rpc),patch.object(bridge,'close') as close,patch('codex_bridge.INTERRUPT_TIMEOUT_S',.02):
                    with self.assertRaises(BridgeError):
                        bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                            deadline=time.monotonic()+1,observer=lambda _:None,cancel_event=cancelled)
                    self.assertEqual(close.called,not confirmed)
                bridge._process=bridge._scratch=None

    def test_cancel_interrupts_inflight_turn(self):
        bridge=CodexBridge(None)
        bridge._scratch=tempfile.TemporaryDirectory()
        self.addCleanup(bridge.close)
        bridge._models={MODEL:{'supportedReasoningEfforts':[{'reasoningEffort':'high'}]}}
        cancelled=threading.Event();methods=[]
        def rpc(method,params,deadline):
            methods.append(method)
            if method=='account/read':return {'account':{'type':'chatgpt'}}
            if method=='account/rateLimits/read':return {'ordinaryUsageAllowed':True,'rateLimits':{'primary':{'usedPercent':0}}}
            if method=='thread/start':return {'thread':{'id':'test-thread'},'model':MODEL}
            if method=='turn/start':
                cancelled.set()
                return {'turn':{'id':'test-turn'}}
            return {}
        with patch.object(bridge,'start'),patch.object(bridge,'_rpc',side_effect=rpc):
            with self.assertRaises(BridgeError) as failure:
                bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                    deadline=time.monotonic()+1,observer=lambda _:None,cancel_event=cancelled)
        self.assertEqual(failure.exception.code,'cancelled')
        self.assertEqual(methods,['account/read','account/rateLimits/read','thread/start','turn/start','turn/interrupt','thread/unsubscribe'])
        self.assertFalse(bridge._calls)

    def test_precancelled_turn_never_starts(self):
        bridge=CodexBridge(None);cancelled=threading.Event();cancelled.set()
        with patch.object(bridge,'start') as start:
            with self.assertRaises(BridgeError):
                bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                    deadline=time.monotonic()+1,observer=lambda _:None,cancel_event=cancelled)
            start.assert_not_called()


if __name__=='__main__':unittest.main()
