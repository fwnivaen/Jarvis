"""Synthetic evaluator execution; no live model or learning-benefit claim."""
import copy
import tempfile
from pathlib import Path
import unittest

from execution_control import ControlError,digest
from execution_evaluation import ARMS,run_protected,promotion_report,validate_splits,verify_result,paired_interval
from tools.prepare_evaluation import cases,prepare

BUDGETS={'seconds':120,'tokens':24000,'tools':12,'model_calls':4}
REQUIREMENTS={arm:{'engine':'fixture','model':'scripted','tools':'v1'} for arm in ARMS}


class EvaluationFixtures(unittest.TestCase):
    def setUp(self):self.splits=cases();self.protected=self.splits['protected'];self.observed=[]

    def execute(self,inputs,budgets):
        self.observed.append(copy.deepcopy(inputs))
        # Scripted fixture reads evidence, never a protected expected answer.
        number=int(inputs['notes'][0]['text'].split('there are ')[1].split()[0])
        unknown='delivery date' in inputs['question']
        arithmetic='subtracted' in inputs['question']
        answer='unknown' if unknown else str(number-2 if arithmetic else number)
        result={'answer':answer,'nodes':[] if unknown else [1],'about_notes':not unknown,
            'evidence':[] if unknown else [{'node':1,'quote':inputs['notes'][0]['text'].split('\n')[0]}],
            'calculations':[{'expression':str(number)+'-2','result':str(number-2)}] if arithmetic else []}
        return {'result':result,'tokens':0,'cost_microunits':None,'tool_calls':0,'model_calls':0,
            'unauthorized_effects':0,'receipt_hashes':[],'model_backed':False,'requirements':REQUIREMENTS['current_frozen']}

    def evaluate(self):
        return run_protected(self.protected,{arm:self.execute for arm in ARMS},requirements=REQUIREMENTS,
            budgets=BUDGETS,setup_cost_microunits=None,model_backed=False)

    def test_24_topic_disjoint_cases_and_private_files(self):
        self.assertEqual(sum(map(len,self.splits.values())),24);validate_splits(self.splits)
        bad=copy.deepcopy(self.splits);bad['protected'][0]['topic']=bad['training'][0]['topic']
        with self.assertRaises(ControlError):validate_splits(bad)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'evaluation';manifest=prepare(root)
            self.assertEqual(manifest['splits']['protected']['case_count'],8)
            self.assertEqual((root/'protected-evaluator-only/protected.json').stat().st_mode&0o777,0o600)
            self.assertFalse((root/'proposer-approved/protected.json').exists())

    def test_five_arms_three_repetitions_execute_without_exposing_expectations(self):
        result=self.evaluate()
        self.assertEqual(len(self.observed),120);self.assertTrue(all(set(x)=={'question','notes'} for x in self.observed))
        self.assertTrue(result['complete']);self.assertFalse(result['model_backed']);self.assertFalse(result['all_costs_counted'])
        self.assertIsNone(result['total_cost_microunits'])
        self.assertTrue(all(v['success']==1 for v in result['summaries'].values()))
        self.assertNotIn('sealed units',str(result))
        with self.assertRaises(ControlError):promotion_report(result,candidate_hash=digest('candidate'),parent_hash=None,scope='fixture',evaluator_key='synthetic')

    def test_fabrication_unauthorized_effect_and_excess_budget_fail(self):
        case=self.protected[0];observation=self.execute(case['input'],BUDGETS)
        observation['result']['evidence'][0]['quote']='invented'
        self.assertIn('fabricated_evidence',verify_result(case,observation['result'])[1])
        def unsafe(inputs,budgets):
            value=self.execute(inputs,budgets);value['unauthorized_effects']=1;value['tool_calls']=13;return value
        result=run_protected(self.protected,{arm:unsafe for arm in ARMS},requirements=REQUIREMENTS,budgets=BUDGETS)
        self.assertTrue(all(v['success']==0 and v['critical_failures']>0 for v in result['summaries'].values()))

    def test_report_counts_all_comparisons_and_rejects_version_changes(self):
        def accounted(inputs,budgets):
            value=self.execute(inputs,budgets);value.update(cost_microunits=2,model_backed=True);return value
        result=run_protected(self.protected,{arm:accounted for arm in ARMS},requirements=REQUIREMENTS,
            budgets=BUDGETS,setup_cost_microunits=17,model_backed=True)
        report,_=promotion_report(result,candidate_hash=digest('candidate'),parent_hash=None,scope='fixture',evaluator_key='synthetic')
        self.assertEqual(report['total_cost'],257);self.assertEqual(report['executions'],48)
        result['requirements']['current_learned']['model']='different'
        with self.assertRaises(ControlError):promotion_report(result,candidate_hash=digest('candidate'),parent_hash=None,scope='fixture',evaluator_key='synthetic')

    def test_case_cluster_interval_does_not_triple_independent_topic_count(self):
        interval=paired_interval([0]*8,[1]*8)
        self.assertEqual(interval['case_count'],8);self.assertEqual(interval['low'],1);self.assertEqual(interval['high'],1)


if __name__=='__main__':unittest.main()
