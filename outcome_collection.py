"""Opt-in minimized workflow outcomes; no raw transcripts, answers or notes."""
from pathlib import Path

from execution_control import feature_flags,digest
from learning_gate import LearningStore

ROOT=Path(__file__).resolve().parent/'.local'
FLAGS=ROOT/'execution-flags.json'
STORE=ROOT/'learning'/'records.sqlite'
MILLISECONDS_PER_SECOND=1000


def capture_execution(run,status,*,flags_path=FLAGS,store_path=STORE):
    """Common opt-in scheduler hook for either executor; scope is hashed."""
    if not feature_flags(flags_path)['outcome_collection']:return 'off'
    outcome={'complete':'success','failed':'failure','cancelled':'cancelled','interrupted':'unknown'}.get(run['status'],'unknown')
    verified=run['status']=='complete' and bool(status.get('result')) and status.get('settled') is True
    if outcome=='success' and not verified:outcome='unknown'
    versions=run['versions']
    complete=status.get('usage_complete') is True and type(status.get('total_tokens')) is int
    record={'run_hash':digest(run['id']),'status':outcome,'engine_version':digest(versions['engine']),
        'model_version':digest(versions['model']),'tool_version':digest(versions['tools']),
        'behavior_hash':digest(versions['behavior']),
        'latency_ms':max(0,int((run.get('ended_at',run['created_at'])-run['created_at'])*MILLISECONDS_PER_SECOND)),
        'tokens':status['total_tokens'] if complete else None,'usage_complete':complete,'cost_microunits':None,
        'verified':verified,'receipt_hashes':[],
        'source_hashes':[digest(r['revision']) for r in (status.get('result') or {}).get('source_refs',[]) if 'revision' in r]}
    store=LearningStore(store_path)
    try:store.outcome(digest([run['project_id'],run['conversation_id']]),record)
    finally:store.close()
    return 'stored'


def capture(run,*,flags_path=FLAGS,store_path=STORE,scope='local/default'):
    if not feature_flags(flags_path)['outcome_collection']:return 'off'
    agents=list(run['agents'].values())
    complete=bool(agents) and all(r.get('usage_reported') and not r.get('unreported_attempts') for r in agents)
    status={'complete':'success','failed':'failure','cancelled':'cancelled','interrupted':'unknown'}.get(run['status'],'unknown')
    if run.get('error') in {'disconnected','unavailable','storage_unavailable'}:status='infrastructure_outage'
    verified=run['status']=='complete' and bool(run.get('result'))
    if status=='success' and not verified:status='unknown'
    versions=run.get('versions',{})
    record={'run_hash':digest(run['id']),'status':status,'engine_version':versions.get('engine','legacy-unversioned'),
        'model_version':digest({r['slot']:r.get('model') for r in agents}),
        'tool_version':versions.get('tools','legacy-unversioned'),'behavior_hash':versions.get('behavior',digest('incumbent')),
        'latency_ms':max(0,int((run.get('ended_at',run['created_at'])-run['created_at'])*MILLISECONDS_PER_SECOND)),
        'tokens':sum(r.get('tokens',0) for r in agents) if complete else None,'usage_complete':complete,
        'cost_microunits':None,'verified':verified,'receipt_hashes':[],
        'source_hashes':[digest(r['revision']) for r in (run.get('result') or {}).get('source_refs',[]) if 'revision' in r]}
    # Missing cost/receipts stay unknown; these records alone cannot pass promotion.
    store=LearningStore(store_path)
    try:store.outcome(scope,record)
    finally:store.close()
    return 'stored'
