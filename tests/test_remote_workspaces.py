"""Fixture provider only: no claim about Docker/Linux/browser isolation."""
import base64
from pathlib import Path
import tempfile
import unittest

from remote_workspaces import WorkspaceManager,WorkspaceError,public_url,MAX_ACTIONS

RUN='a'*24
WORKER='b'*24
PNG=b'\x89PNG\r\n\x1a\nsynthetic'


class Provider:
    def __init__(self):self.containers={};self.calls=[];self.fail_destroy=False;self.fail_action=False
    def create(self,row):
        self.containers[row['id']]={'id':row['id'],'expires_at':row['expires_at']}
        return {'endpoint':'http://127.0.0.1:4444'}
    def webdriver(self,row,method,path,body=None):
        self.calls.append((row['id'],method,path))
        if self.fail_action:raise WorkspaceError('simulated')
        if path=='/status':return {'ready':True}
        if path=='/session':return {'sessionId':'unique-'+row['id']}
        if path.endswith('/screenshot'):return base64.b64encode(PNG).decode()
        return 'Synthetic fixture'
    def destroy(self,wid):
        if self.fail_destroy:raise WorkspaceError('simulated cleanup')
        self.containers.pop(wid,None);return True
    def inventory(self):return list(self.containers.values())


class WorkspaceFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=[100.0];self.provider=Provider();self.path=Path(self.tmp.name)/'workspaces.sqlite'
        self.manager=WorkspaceManager(self.path,self.provider,clock=lambda:self.now[0]);self.addCleanup(self.manager.close)
        self.args=dict(run_id=RUN,worker_id=WORKER,generation=1,expires_at=200)
        self.row=self.manager.create('request',**self.args)
        self.lease={k:self.args[k] for k in ('run_id','worker_id','generation')}

    def ready(self):return self.manager.ready(self.row['id'])

    def test_duplicate_create_does_not_create_session_or_container(self):
        self.assertEqual(self.manager.create('request',**self.args)['id'],self.row['id'])
        self.assertEqual(len(self.provider.containers),1)
        self.assertEqual(self.provider.calls,[])
        with self.assertRaises(WorkspaceError):self.manager.create('request',**dict(self.args,generation=2))

    def test_capacity_queues_extra_work(self):
        with self.assertRaises(WorkspaceError):self.manager.create('second',**self.args)

    def test_readiness_and_watch_share_exact_session_without_input(self):
        row=self.ready()
        self.assertEqual(self.manager.watch(row['id'],**self.lease),PNG)
        self.assertEqual(self.provider.calls[-1][2],'/session/'+row['session']+'/screenshot')
        self.assertEqual(sum(path=='/session' for _,_,path in self.provider.calls),1)
        self.ready()
        self.assertEqual(sum(path=='/session' for _,_,path in self.provider.calls),1)

    def test_watch_cannot_start_work(self):
        with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**self.lease)
        self.assertEqual(self.provider.calls,[])

    def test_foreign_worker_run_and_generation_rejected(self):
        self.ready()
        for kw in ({'worker_id':'c'*24},{'run_id':'c'*24},{'generation':2}):
            with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**dict(self.lease,**kw))

    def test_expiry_is_worker_owned_and_reaped(self):
        self.ready();self.now[0]=201
        with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**self.lease)
        self.assertEqual(self.manager.reconcile(),[])
        self.assertEqual(self.manager.get(self.row['id'])['cleanup'],'complete')

    def test_container_failure_retains_cleanup_pending_until_confirmed(self):
        self.ready();self.provider.fail_destroy=True
        row=self.manager.destroy(self.row['id'])
        self.assertEqual(row['cleanup'],'pending');self.assertFalse(row['container_terminated'])
        self.provider.fail_destroy=False
        self.assertEqual(self.manager.reconcile(),[])
        self.assertEqual(self.manager.get(row['id'])['state'],'destroyed')

    def test_orphan_reaper_after_restart(self):
        orphan='e'*24;self.provider.containers[orphan]={'id':orphan,'expires_at':999}
        self.manager.reconcile();self.assertNotIn(orphan,self.provider.containers)
        reopened=WorkspaceManager(self.path,self.provider,clock=lambda:self.now[0])
        try:self.assertEqual(reopened.get(self.row['id'])['run_id'],RUN)
        finally:reopened.close()

    def test_browser_failure_leaves_action_uncertain_and_no_retry(self):
        self.ready();self.provider.fail_action=True
        with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**self.lease)
        self.provider.fail_action=False
        with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**self.lease)

    def test_inputs_navigation_and_scripts_disabled_until_gates(self):
        self.ready()
        for kind in ('navigate','click','type','execute','takeover','download'):
            with self.assertRaises(WorkspaceError):self.manager.action(self.row['id'],kind=kind,value='untrusted',**self.lease)

    def test_action_quota_is_durable(self):
        self.ready()
        for _ in range(MAX_ACTIONS):self.manager.action(self.row['id'],kind='inspect',**self.lease)
        with self.assertRaises(WorkspaceError):self.manager.watch(self.row['id'],**self.lease)

    def test_private_metadata_file_redirect_and_rebinding_urls(self):
        def resolver(host,port,**kwargs):return [(None,None,None,None,('127.0.0.1',port))]
        for value in ('file:///etc/passwd','http://allowed.example','https://user:secret@allowed.example',
                      'https://169.254.169.254','https://allowed.example:444','https://allowed.example'):
            with self.assertRaises(WorkspaceError):public_url(value,{'allowed.example'},resolver)
        def mixed(host,port,**kwargs):return [(0,0,0,0,('8.8.8.8',port)),(0,0,0,0,('10.0.0.1',port))]
        with self.assertRaises(WorkspaceError):public_url('https://allowed.example',{'allowed.example'},mixed)


if __name__=='__main__':unittest.main()
