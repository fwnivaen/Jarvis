"""Offline official GEPA integration. Never receives protected cases or promotion keys.

Call optimize_reviewed with reviewed evaluator/proposer callables in the isolated
GEPA environment. No dynamic import hooks, pickle loading, state resume or hosted
tracing. The CLI fixture validates plumbing only, not optimization efficacy.
"""
import contextlib
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from execution_control import ControlError
from learning_gate import ALLOWED_COMPONENTS,MAX_COMPONENT_CHARS

MAX_METRIC_CALLS=64
MIN_SPLIT_CASES=8
SEED=42
MAX_FEEDBACK_CHARS=1000


def optimize_reviewed(seed,training,development,evaluate,propose,*,max_metric_calls=MAX_METRIC_CALLS):
    from gepa import optimize
    from gepa.core.adapter import EvaluationBatch
    if (not isinstance(seed,dict) or not seed or set(seed)-ALLOWED_COMPONENTS
            or any(not isinstance(v,str) or len(v)>MAX_COMPONENT_CHARS for v in seed.values())
            or not 0<max_metric_calls<=MAX_METRIC_CALLS):raise ControlError('Invalid proposal scope or budget.')
    if len(training)<MIN_SPLIT_CASES or len(development)<MIN_SPLIT_CASES:raise ControlError('Eight training and development examples required.')
    all_cases=training+development
    if any(set(x)!={'id','topic','input'} for x in all_cases):raise ControlError('Only approved minimized train/development inputs accepted.')
    if len({x['id'] for x in all_cases})!=len(all_cases) or len({x['topic'] for x in all_cases})!=len(all_cases):raise ControlError('Evaluation IDs and topics must be disjoint.')
    counts={'evaluations':0,'proposals':0,'reflection_calls':0,'total_cost_microunits':0,'tokens':0}
    class Adapter:
        propose_new_texts=None
        def evaluate(self,batch,candidate,capture_traces=False):
            if counts['evaluations']+len(batch)>max_metric_calls:raise ControlError('Evaluation budget exhausted.')
            outputs=[];scores=[];traces=[]
            for case in batch:
                result=evaluate(candidate,case)
                if set(result)!={'score','feedback','cost_microunits','tokens'}:raise ControlError('Missing evaluation accounting.')
                if not 0<=result['score']<=1 or result['cost_microunits']<0 or result['tokens']<0:raise ControlError('Invalid evaluation accounting.')
                counts['evaluations']+=1;counts['total_cost_microunits']+=result['cost_microunits'];counts['tokens']+=result['tokens']
                outputs.append({'case_id':case['id']});scores.append(result['score'])
                traces.append({'feedback':str(result['feedback'])[:MAX_FEEDBACK_CHARS]})
            return EvaluationBatch(outputs=outputs,scores=scores,trajectories=traces if capture_traces else None)
        def make_reflective_dataset(self,candidate,batch,components_to_update):
            return {name:batch.trajectories for name in components_to_update}
    def bounded_propose(candidate,reflective_dataset,components_to_update):
        result=propose(candidate,reflective_dataset,components_to_update)
        if set(result)!={'components','cost_microunits','tokens'}:raise ControlError('Missing proposal accounting.')
        components=result['components']
        if (set(components)-set(seed) or any(not isinstance(v,str) or len(v)>MAX_COMPONENT_CHARS for v in components.values())
                or result['cost_microunits']<0 or result['tokens']<0):raise ControlError('Proposal exceeded scope.')
        counts['proposals']+=1;counts['reflection_calls']+=1
        counts['total_cost_microunits']+=result['cost_microunits'];counts['tokens']+=result['tokens']
        return components
    # run_dir=None prevents checkpoint/pickle resume. All proposal/rollout costs
    # are accumulated above; protected final comparisons are a separate service.
    with contextlib.redirect_stdout(io.StringIO()):
        result=optimize(seed_candidate=seed,trainset=training,valset=development,adapter=Adapter(),
            custom_candidate_proposer=bounded_propose,max_metric_calls=max_metric_calls,
            reflection_minibatch_size=2,run_dir=None,use_cloudpickle=False,
            use_wandb=False,use_mlflow=False,track_best_outputs=False,display_progress_bar=False,seed=SEED)
    return {'candidate':result.best_candidate,'accounting':counts,'scope':'offline proposal only; protected validation and reviewed promotion still required'}


def fixture():
    training=[{'id':'train-'+str(i),'topic':'training-topic-'+str(i),'input':'synthetic'} for i in range(8)]
    development=[{'id':'dev-'+str(i),'topic':'development-topic-'+str(i),'input':'synthetic'} for i in range(8)]
    def evaluate(candidate,case):
        return {'score':float('revision' in candidate['instructions']),'feedback':'Check the source revision.',
                'cost_microunits':0,'tokens':0}
    def propose(candidate,data,components):
        return {'components':{'instructions':'Read source revision before answering.'},'cost_microunits':0,'tokens':0}
    return optimize_reviewed({'instructions':'Answer immediately.'},training,development,evaluate,propose)


if __name__=='__main__':
    if sys.argv[1:]!=['--fixture']:raise SystemExit('Only --fixture is exposed; live hooks require reviewed operator integration.')
    print(json.dumps(fixture(),sort_keys=True))
