"""Promotion/security fixtures with synthetic signed reports; no learning claim."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from execution_control import ControlError,digest
from learning_gate import LearningStore,signature

ROOT=Path(__file__).resolve().parents[1]
REQUIREMENTS={'engine':'fixture','model':'fixture','tools':'fixture-v1'}
EVALUATOR='synthetic-evaluator-key'
REVIEWER='synthetic-reviewer-key'


class LearningFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=LearningStore(Path(self.tmp.name)/'learning.sqlite');self.addCleanup(self.store.close)
        self.bundle=self.propose()

    def propose(self,parent=None):
        return self.store.propose(scope='project/research',parent_hash=parent,components={'instructions':'Check revisions.'},
            requirements=REQUIREMENTS,evidence=[digest('synthetic evidence')],expires_at=time.time()+60)

    def report(self,bundle=None,**changes):
        b=bundle or self.bundle
        data=dict(candidate_hash=b['hash'],parent_hash=b['parent_hash'],scope=b['scope'],requirements=REQUIREMENTS,
            protected_hash=digest('fresh protected set '+b['hash']),case_count=8,repetitions=3,executions=48,
            critical_failures=0,families={'research':{'baseline':.8,'candidate':.95,'floor':.9}},
            baseline_success=.8,candidate_success=.95,baseline_cost=100,candidate_cost=100,total_cost=250,
            all_costs_counted=True,equivalent_budgets=True,model_backed=True,complete=True)
        data.update(changes);return data

    def promote(self,bundle=None,report=None):
        b=bundle or self.bundle;r=report or self.report(b)
        review={'candidate_hash':b['hash'],'report_hash':digest(r),'approved':True}
        return self.store.promote(b['hash'],r,signature(EVALUATOR,r),evaluator_key=EVALUATOR,
            review_receipt=review,review_mac=signature(REVIEWER,review),reviewer_key=REVIEWER)

    def test_candidate_does_not_activate_itself(self):
        self.assertIsNone(self.store.current('project/research'))
        with self.assertRaises(ControlError):
            self.store.promote(self.bundle['hash'],self.report(),'fake',evaluator_key=EVALUATOR,
                review_receipt={},review_mac='fake',reviewer_key=REVIEWER)

    def test_incomplete_invariant_and_family_regression_rejected(self):
        for changes in ({'complete':False},{'critical_failures':1},{'model_backed':False},{'executions':47},
                        {'all_costs_counted':False},{'families':{'research':{'baseline':.98,'candidate':.95,'floor':.9}}},
                        {'families':{'research':{'baseline':.5,'candidate':.8,'floor':0}}}):
            with self.subTest(changes=changes),self.assertRaises(ControlError):self.promote(report=self.report(**changes))
        self.assertIsNone(self.store.current('project/research'))

    def test_inconclusive_results_retain_incumbent(self):
        with self.assertRaises(ControlError):self.promote(report=self.report(baseline_success=.94,candidate_success=.95))
        self.assertIsNone(self.store.current('project/research'))

    def test_atomic_promotion_pins_old_run_bundle_and_reviewed_rollback(self):
        old=self.promote();pinned=dict(old)
        new=self.propose(old['hash']);self.promote(new)
        self.assertEqual(pinned['hash'],old['hash'])
        self.assertEqual(self.store.current(old['scope'])['hash'],new['hash'])
        receipt={'scope':old['scope'],'from_hash':new['hash'],'to_hash':old['hash'],'rollback':True}
        self.store.rollback(old['scope'],review_receipt=receipt,review_mac=signature(REVIEWER,receipt),reviewer_key=REVIEWER)
        self.assertEqual(self.store.current(old['scope'])['hash'],old['hash'])

    def test_stale_parent_and_reused_protected_tests_rejected(self):
        self.promote()
        stale=self.propose(None)
        with self.assertRaises(ControlError):self.promote(stale)
        child=self.propose(self.bundle['hash'])
        with self.assertRaises(ControlError):self.promote(child,self.report(child,protected_hash=self.report()['protected_hash']))

    def test_security_code_and_budget_components_cannot_be_changed(self):
        for key in ('permissions','code','verifier','budget','identity','protected_tests'):
            with self.assertRaises(ControlError):
                self.store.propose(scope='project',parent_hash=None,components={key:'malicious'},requirements=REQUIREMENTS,
                    evidence=[digest('x')],expires_at=time.time()+60)

    def test_scope_and_requirement_separation(self):
        self.promote()
        self.assertIsNone(self.store.current('other-project/research'))
        self.assertIsNone(self.store.current(self.bundle['scope'],dict(REQUIREMENTS,model='different')))

    def test_outcomes_reject_raw_data_and_false_success(self):
        record=dict(run_hash=digest('run'),status='success',engine_version='v1',model_version='fixture',tool_version='v1',
            behavior_hash=digest('behavior'),latency_ms=20,tokens=30,usage_complete=True,cost_microunits=0,verified=True,
            receipt_hashes=[digest('receipt')],source_hashes=[digest('source')])
        self.store.outcome('project/research',record)
        for extra in ({'prompt':'remember this forever'},{'verified':False},{'source_hashes':['private note text']}):
            with self.assertRaises(ControlError):self.store.outcome('project/research',dict(record,**extra))
        self.store.erase_scope('project/research')
        for table in ('bundles','outcomes','promotions','active'):
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)

    @unittest.skipUnless((ROOT/'.local/gepa-venv/bin/python').exists(),'Optional pinned GEPA unavailable')
    def test_real_gepa_offline_plumbing_no_protected_inputs_or_pickle(self):
        p=subprocess.run([str(ROOT/'.local/gepa-venv/bin/python'),'-I',str(ROOT/'optional/gepa/proposer.py'),'--fixture'],
            capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        self.assertIn('revision',result['candidate']['instructions'])
        self.assertLessEqual(result['accounting']['evaluations'],64)
        self.assertGreater(result['accounting']['proposals'],0)
        self.assertIsNone(self.store.current('project/research'))


if __name__=='__main__':unittest.main()
