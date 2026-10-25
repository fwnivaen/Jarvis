"""Local operator-spool failure fixtures, not a Linux deployment check."""
import json
from pathlib import Path
import tempfile
import unittest

from execution_control import ControlStore
from execution_scheduler import Scheduler
from tools.run_remote_controller import ingest_spool

VERSIONS={'engine':'fixture','model':'fixture','tools':'fixture','behavior':'fixture'}


class SpoolFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.spool=self.root/'spool';self.spool.mkdir(mode=0o700)
        self.store=ControlStore(self.root/'control.sqlite');self.addCleanup(self.store.close)
        self.scheduler=Scheduler(self.store,{'langgraph':lambda run:None})

    def ingest(self):return ingest_spool(self.scheduler,self.spool,duration_s=60,versions=VERSIONS,permissions=[])

    def write(self,name,data):
        path=self.spool/name;path.write_text(json.dumps(data));path.chmod(0o600);return path

    def test_malformed_file_is_quarantined_without_losing_valid_admission(self):
        self.write('bad.json',{'private_unknown_field':'must not log'})
        self.write('good.json',{'request_key':'one','conversation_id':'c','project_id':'p','question':'Synthetic'})
        self.assertEqual(self.ingest(),{'accepted':1,'rejected':1})
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
        self.assertEqual(len(list(self.spool.glob('*.rejected-*'))),1)
        self.assertEqual(self.ingest(),{'accepted':0,'rejected':0})

    def test_symlink_and_insecure_file_never_reach_scheduler(self):
        outside=self.root/'private.json';outside.write_text('private sentinel')
        (self.spool/'linked.json').symlink_to(outside)
        p=self.write('insecure.json',{'request_key':'bad'});p.chmod(0o644)
        self.assertEqual(self.ingest(),{'accepted':0,'rejected':2})
        self.assertEqual(outside.read_text(),'private sentinel')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],0)


if __name__=='__main__':unittest.main()
