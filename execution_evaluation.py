"""Trusted offline paired evaluator; protected expectations never reach executors.

Review/run under a separate evaluator OS identity. Callables are operator-owned,
not import paths or code supplied by a candidate. This module cannot promote.
"""
import copy
import math
import random
import statistics
import time

from execution_control import ControlError, digest
from learning_gate import PROTECTED_REPETITIONS, signature, valid_hash
from ultra import checked,CheckFailure

ARMS=('current_frozen','current_learned','deepagents_frozen','deepagents_learned','manual_fix')
SPLITS=('training','development','protected')
CASES_PER_SPLIT=8
BOOTSTRAP_SAMPLES=2000
CONFIDENCE=.95
RANDOM_SEED=317
MAX_CALL_SECONDS=120
MAX_REPORTED_TOKENS=24000
MAX_TOOL_CALLS=12
MAX_MODEL_CALLS=4
MAX_TOTAL_EXECUTIONS=120
MAX_TOTAL_SECONDS=MAX_TOTAL_EXECUTIONS*MAX_CALL_SECONDS
FAMILY_SUCCESS_FLOOR=.9
LATENCY_QUANTILE=.95
MILLISECONDS_PER_SECOND=1000
RESULT_FIELDS=frozenset({'answer','nodes','evidence','calculations','about_notes'})


def validate_splits(splits):
    if not isinstance(splits,dict) or set(splits)!=set(SPLITS):raise ControlError('Three evaluation splits required.')
    all_cases=[]
    for name in SPLITS:
        if len(splits[name])!=CASES_PER_SPLIT:raise ControlError('Exactly eight cases per initial split.')
        for case in splits[name]:
            if (set(case)!={'id','topic','family','input','expected'} or not case['id'] or not case['topic']
                    or not isinstance(case['input'],dict) or not isinstance(case['expected'],dict)):
                raise ControlError('Invalid evaluation case.')
        all_cases+=splits[name]
    if len({c['id'] for c in all_cases})!=len(all_cases) or len({c['topic'] for c in all_cases})!=len(all_cases):
        raise ControlError('Case IDs and topics must be disjoint across splits.')
    return digest(splits)


def verify_result(case,result):
    """Deterministic supported-task criteria, separate from the model output."""
    expected=case['expected']
    if not isinstance(result,dict) or set(result)!=RESULT_FIELDS:return False,['invalid_final_schema']
    if not isinstance(result['answer'],str) or type(result['about_notes']) is not bool:return False,['invalid_final_schema']
    if not isinstance(result['nodes'],list) or not isinstance(result['evidence'],list):return False,['invalid_final_schema']
    allowed={n['id']:n for n in case['input']['notes']}
    critical=[]
    if any(type(i) is not int or i not in allowed for i in result['nodes']):critical.append('fabricated_source')
    for evidence in result['evidence']:
        if (not isinstance(evidence,dict) or set(evidence)!={'node','quote'} or type(evidence['node']) is not int or evidence['node'] not in allowed
                or not isinstance(evidence['quote'],str) or not evidence['quote']
                or evidence['quote'] not in allowed[evidence['node']]['text']):critical.append('fabricated_evidence')
    try:checked(result,case['input']['notes'])
    except CheckFailure as error:
        if error.code=='math_check':critical.append('false_calculation')
        return False,sorted(set(critical))
    success=(not critical and set(result['nodes'])==set(expected['nodes'])
        and all(x.casefold() in result['answer'].casefold() for x in expected['answer_contains'])
        and all(x.casefold() not in result['answer'].casefold() for x in expected['answer_excludes'])
        and set(result['nodes'])<={e['node'] for e in result['evidence']})
    return success,sorted(set(critical))


def paired_interval(baseline,candidate):
    """Case-cluster bootstrap; repetitions are not independent new topics."""
    if len(baseline)!=len(candidate) or not baseline:raise ControlError('Paired cases required.')
    deltas=[b-a for a,b in zip(baseline,candidate)]
    rng=random.Random(RANDOM_SEED)
    samples=sorted(statistics.mean(rng.choices(deltas,k=len(deltas))) for _ in range(BOOTSTRAP_SAMPLES))
    tail=(1-CONFIDENCE)/2
    return {'estimate':statistics.mean(deltas),'low':samples[int(BOOTSTRAP_SAMPLES*tail)],
        'high':samples[min(BOOTSTRAP_SAMPLES-1,int(BOOTSTRAP_SAMPLES*(1-tail)))],
        'confidence':CONFIDENCE,'method':'paired case-cluster bootstrap','case_count':len(deltas)}


def run_protected(cases,executors,*,requirements,budgets,setup_cost_microunits=None,model_backed=False):
    """Execute every arm three times; minimized results only, no answer logging.

    Each trusted executor receives ONLY question/evidence and the same budgets.
    It must return outcome + independently collected usage/operation trace. Unknown
    costs remain None, making promotion ineligible. No credentials in results.
    """
    if (len(cases)!=CASES_PER_SPLIT or set(executors)!=set(ARMS) or set(requirements)!=set(ARMS)
            or set(budgets)!={'seconds','tokens','tools','model_calls'}
            or any(type(v) is not int or v<=0 for v in budgets.values())
            or budgets['seconds']>MAX_CALL_SECONDS or budgets['tokens']>MAX_REPORTED_TOKENS
            or budgets['tools']>MAX_TOOL_CALLS or budgets['model_calls']>MAX_MODEL_CALLS):
        raise ControlError('Unsupported comparison or budget.')
    if setup_cost_microunits is not None and (type(setup_cost_microunits) is not int or setup_cost_microunits<0):
        raise ControlError('Invalid proposal/reflection/retry accounting.')
    if len({c['id'] for c in cases})!=len(cases) or len({c['topic'] for c in cases})!=len(cases):
        raise ControlError('Protected cases must be topic disjoint.')
    started=time.monotonic();records=[]
    for case_index,case in enumerate(cases):
        for repetition in range(PROTECTED_REPETITIONS):
            # Rotate arm order to reduce warm-cache/order bias. No parallelism.
            order=ARMS[(case_index+repetition)%len(ARMS):]+ARMS[:(case_index+repetition)%len(ARMS)]
            for arm in order:
                if len(records)>=MAX_TOTAL_EXECUTIONS or time.monotonic()-started>=MAX_TOTAL_SECONDS:
                    raise ControlError('Total evaluation budget exhausted.')
                call_start=time.monotonic()
                try:
                    observation=executors[arm](copy.deepcopy(case['input']),dict(budgets))
                    if set(observation)!={'result','tokens','cost_microunits','tool_calls','model_calls','unauthorized_effects','receipt_hashes','model_backed','requirements'}:
                        raise ControlError('Incomplete observed execution.')
                    if observation['requirements']!=requirements[arm]:raise ControlError('Execution version changed.')
                    for field in ('tool_calls','model_calls','unauthorized_effects'):
                        if type(observation[field]) is not int or observation[field]<0:raise ControlError('Invalid observed counters.')
                    for field in ('tokens','cost_microunits'):
                        if observation[field] is not None and (type(observation[field]) is not int or observation[field]<0):raise ControlError('Invalid usage/cost.')
                    if type(observation['model_backed']) is not bool:raise ControlError('Missing model provenance.')
                    if (not isinstance(observation['receipt_hashes'],list) or any(not valid_hash(h) for h in observation['receipt_hashes'])):
                        raise ControlError('Evidence receipts must be hashes.')
                    success,critical=verify_result(case,observation['result'])
                    elapsed=time.monotonic()-call_start
                    if observation['unauthorized_effects']:critical.append('unauthorized_effect')
                    if (elapsed>budgets['seconds'] or observation['tokens'] is not None and observation['tokens']>budgets['tokens']
                            or observation['tool_calls']>budgets['tools'] or observation['model_calls']>budgets['model_calls']):
                        success=False;critical.append('budget_exceeded')
                    record={'case_hash':digest(case['id']),'family':case['family'],'arm':arm,'repetition':repetition,
                        'success':bool(success and not critical),'critical':critical,'latency_ms':round(elapsed*MILLISECONDS_PER_SECOND),
                        'tokens':observation['tokens'],'cost_microunits':observation['cost_microunits'],
                        'model_backed':observation['model_backed'],'receipt_hashes':observation['receipt_hashes']}
                except Exception:
                    record={'case_hash':digest(case['id']),'family':case['family'],'arm':arm,'repetition':repetition,
                        'success':False,'critical':[],'latency_ms':round((time.monotonic()-call_start)*MILLISECONDS_PER_SECOND),
                        'tokens':None,'cost_microunits':None,'model_backed':False,'receipt_hashes':[],
                        'error':'execution_or_accounting_failed'}
                records.append(record)
    complete=len(records)==MAX_TOTAL_EXECUTIONS
    accounted=setup_cost_microunits is not None and all(r['cost_microunits'] is not None for r in records)
    backed=model_backed and all(r['model_backed'] for r in records)
    summaries={}
    for arm in ARMS:
        rows=[r for r in records if r['arm']==arm]
        latencies=sorted(r['latency_ms'] for r in rows)
        summaries[arm]={'success':statistics.mean(r['success'] for r in rows),'critical_failures':sum(len(r['critical']) for r in rows),
            'p95_ms':latencies[math.ceil(len(latencies)*LATENCY_QUANTILE)-1],
            'cost_microunits':sum(r['cost_microunits'] for r in rows) if all(r['cost_microunits'] is not None for r in rows) else None}
    intervals={}
    for baseline,candidate in (('current_frozen','current_learned'),('deepagents_frozen','deepagents_learned'),('current_frozen','manual_fix')):
        means=lambda arm:[statistics.mean(r['success'] for r in records if r['arm']==arm and r['case_hash']==digest(c['id'])) for c in cases]
        key=baseline+':'+candidate
        intervals[key]=dict(paired_interval(means(baseline),means(candidate)),
            comparison='harness' if requirements[baseline]==requirements[candidate] else 'different-endpoint end-to-end')
    return {'schema_version':1,'protected_hash':digest(cases),'records':records,'summaries':summaries,
        'requirements':copy.deepcopy(requirements),'budgets':dict(budgets),'complete':complete,
        'model_backed':backed,'all_costs_counted':accounted,'intervals':intervals,
        'setup_cost_microunits':setup_cost_microunits,
        'total_cost_microunits':setup_cost_microunits+sum(r['cost_microunits'] for r in records) if accounted else None,
        'limitation':'Initial eight protected topics; no general improvement claim. Executor callables must enforce pre-call budgets and cancellation.'}


def promotion_report(evaluation,*,candidate_hash,parent_hash,scope,baseline='current_frozen',candidate='current_learned',evaluator_key):
    if not evaluation['complete'] or not evaluation['model_backed'] or not evaluation['all_costs_counted']:
        raise ControlError('No model-backed complete-cost promotion evidence.')
    if evaluation['requirements'][baseline]!=evaluation['requirements'][candidate]:raise ControlError('Equivalent endpoint/tool requirements required for harness promotion.')
    rows=[r for r in evaluation['records'] if r['arm'] in (baseline,candidate)]
    families={}
    for family in {r['family'] for r in rows}:
        families[family]={'baseline':statistics.mean(r['success'] for r in rows if r['arm']==baseline and r['family']==family),
            'candidate':statistics.mean(r['success'] for r in rows if r['arm']==candidate and r['family']==family),'floor':FAMILY_SUCCESS_FLOOR}
    report={'candidate_hash':candidate_hash,'parent_hash':parent_hash,'scope':scope,
        'requirements':evaluation['requirements'][candidate],'protected_hash':evaluation['protected_hash'],
        'case_count':CASES_PER_SPLIT,'repetitions':PROTECTED_REPETITIONS,'executions':len(rows),
        'critical_failures':sum(len(r['critical']) for r in evaluation['records']),'families':families,
        'baseline_success':evaluation['summaries'][baseline]['success'],'candidate_success':evaluation['summaries'][candidate]['success'],
        'baseline_cost':evaluation['summaries'][baseline]['cost_microunits'],'candidate_cost':evaluation['summaries'][candidate]['cost_microunits'],
        'total_cost':evaluation['total_cost_microunits'],'all_costs_counted':True,'equivalent_budgets':True,'model_backed':True,'complete':True}
    return report,signature(evaluator_key,report)
