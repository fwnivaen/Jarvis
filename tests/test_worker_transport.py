import json
from pathlib import Path
import secrets
import tempfile
import unittest

from remote_workspaces import WorkspaceManager,WorkspaceError
from worker_transport import WorkerAuth,dispatch,signature
from test_remote_workspaces import Provider


class WorkerTransportFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.manager=WorkspaceManager(Path(self.tmp.name)/'worker.sqlite',Provider());self.addCleanup(self.manager.close)
        self.key=secrets.token_hex(32);self.clock=lambda:100
        self.auth=WorkerAuth(self.manager,self.key,clock=self.clock)
        self.raw=json.dumps({'operation':'reconcile','arguments':{}}).encode()

    def headers(self,stamp='100',nonce='fixture-unique-nonce'):
        return {'X-Jarvis-Time':stamp,'X-Jarvis-Nonce':nonce,'X-Jarvis-Signature':signature(self.key,stamp,nonce,self.raw)}

    def test_valid_auth_and_durable_replay_rejection(self):
        headers=self.headers();self.auth.verify(headers,self.raw)
        reopened=WorkerAuth(self.manager,self.key,clock=self.clock)
        with self.assertRaises(WorkspaceError):reopened.verify(headers,self.raw)

    def test_expired_nan_and_forged_frames_fail_closed(self):
        for stamp in ('0','nan','inf'):
            with self.assertRaises(WorkspaceError):self.auth.verify(self.headers(stamp),self.raw)
        headers=self.headers();headers['X-Jarvis-Signature']='forged'
        with self.assertRaises(WorkspaceError):self.auth.verify(headers,self.raw)
        with self.assertRaises(WorkspaceError):self.auth.verify(self.headers(),self.raw+b' ')

    def test_rpc_has_no_shell_script_or_input_routes(self):
        for name in ('shell','execute','takeover','navigate','create_desktop'):
            with self.assertRaises(WorkspaceError):dispatch(self.manager,{'operation':name,'arguments':{}})
        with self.assertRaises(WorkspaceError):dispatch(self.manager,{'operation':'reconcile','arguments':{},'permissions':['admin']})
        self.assertEqual(dispatch(self.manager,{'operation':'reconcile','arguments':{}}),[])

    def test_sample_worker_key_cannot_activate(self):
        with self.assertRaises(WorkspaceError):WorkerAuth(self.manager,'OPERATOR_MUST_GENERATE_NEW_PRIVATE_32_BYTE_OR_LONGER_KEY')


if __name__=='__main__':unittest.main()
