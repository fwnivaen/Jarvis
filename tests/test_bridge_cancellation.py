"""Verify transport cancellation interrupts the actual turn protocol boundary."""
import threading
import tempfile
import time
import unittest
from unittest.mock import patch
from codex_bridge import CodexBridge, BridgeError

MODEL='gpt-6-luna'


class CancellationTests(unittest.TestCase):
    def test_cancel_interrupts_inflight_turn(self):
        bridge=CodexBridge(None)
        bridge._scratch=tempfile.TemporaryDirectory()
        self.addCleanup(bridge.close)
        bridge._models={MODEL:{'supportedReasoningEfforts':[{'reasoningEffort':'high'}]}}
        cancelled=threading.Event();methods=[]
        def rpc(method,params,deadline):
            methods.append(method)
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
        self.assertEqual(methods,['thread/start','turn/start','turn/interrupt','thread/unsubscribe'])
        self.assertFalse(bridge._calls)

    def test_precancelled_turn_never_starts(self):
        bridge=CodexBridge(None);cancelled=threading.Event();cancelled.set()
        with patch.object(bridge,'start') as start:
            with self.assertRaises(BridgeError):
                bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                    deadline=time.monotonic()+1,observer=lambda _:None,cancel_event=cancelled)
            start.assert_not_called()


if __name__=='__main__':unittest.main()
