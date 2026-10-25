import tempfile
from pathlib import Path
import unittest

from execution_control import ControlStore,ControlError
from execution_scheduler import Scheduler


class Executor:
    def __init__(self):self.started=0;self.cancelled=False;self.state='queued';self.settled=False
    def start(self,**kwargs):self.started+=1;self.state='running';return self.status()
    def status(self):return {'status':self.state,'settled':self.settled,'result':{'answer':'synthetic'}}
    def cancel(self):self.cancelled=True;self.state='cancelled'


class SchedulerFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ControlStore(Path(self.tmp.name)/'scheduler.sqlite');self.addCleanup(self.store.close)
        self.executor=Executor();self.scheduler=Scheduler(self.store,{'fixture':lambda run:self.executor})
        self.args=dict(engine='fixture',conversation_id='c',project_id='p',versions={'engine':'v1','model':'fixture','tools':'v1','behavior':'v1'},permissions=[],duration_s=60)

    def test_duplicate_requests_are_single_start_and_survive_client_absence(self):
        first,_=self.scheduler.enqueue('key','Synthetic',**self.args)
        second,created=self.scheduler.enqueue('key','Synthetic',**self.args)
        self.assertEqual(first,second);self.assertFalse(created)
        for _ in range(3):self.scheduler.tick()
        self.assertEqual(self.executor.started,1)
        self.executor.state='complete';self.executor.settled=True;self.scheduler.tick()
        self.assertEqual(self.store.get(first['id'])['status'],'complete')
        with self.assertRaises(ControlError):self.scheduler.enqueue('key','Changed',**self.args)

    def test_cancel_waits_for_underlying_settlement_before_next_start(self):
        run,_=self.scheduler.enqueue('first','First',**self.args)
        self.scheduler.enqueue('second','Second',**self.args)
        self.scheduler.tick();self.scheduler.cancel(run['id']);self.scheduler.tick()
        self.assertEqual(self.store.get(run['id'])['status'],'cancelling')
        self.assertEqual(self.executor.started,1)
        self.executor.settled=True;self.scheduler.tick()
        self.assertEqual(self.store.get(run['id'])['status'],'cancelled')

    def test_restart_marks_interrupted_does_not_silently_replay(self):
        run,_=self.scheduler.enqueue('key','Synthetic',**self.args);self.scheduler.tick()
        reopened=Scheduler(self.store,{'fixture':lambda run:self.executor});reopened.recover();reopened.tick()
        self.assertEqual(self.executor.started,1)
        self.assertEqual(self.store.get(run['id'])['status'],'interrupted')

    def test_queued_cancel_never_starts_executor(self):
        run,_=self.scheduler.enqueue('key','Synthetic',**self.args)
        self.scheduler.cancel(run['id']);self.scheduler.tick()
        self.assertEqual(self.executor.started,0)

    def test_collection_failure_is_observable_without_blocking_delivery(self):
        def failed(run,status):raise OSError('synthetic storage outage')
        self.scheduler.outcome_hook=failed
        run,_=self.scheduler.enqueue('key','Synthetic',**self.args);self.scheduler.tick()
        self.executor.state='complete';self.executor.settled=True;self.scheduler.tick()
        self.assertEqual(self.store.get(run['id'])['status'],'complete')
        self.assertEqual(self.store.db.execute('SELECT status FROM collection_status WHERE run_id=?',(run['id'],)).fetchone()[0],'unavailable')


if __name__=='__main__':unittest.main()
