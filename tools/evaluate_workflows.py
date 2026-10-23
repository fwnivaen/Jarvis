"""Bounded deterministic graph benchmark; model boundary is synthetic, no model spending.

Use the separate documented HTTP examples for real model acceptance checks.
"""
import json
import resource
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_workflow_runtime import Model, NOTE
from ultra import Settings
from ultra_tools import Registry
from workflow_runtime import WorkflowService, WorkflowError

RUNS=20
CONCURRENT_ATTEMPTS=20
WAIT_S=10
BUSY_MODEL_S=.1
POLL_S=.01


def main():
    settings=replace(Settings(),enabled=True,terminal_monitor_enabled=False)
    model=Model()
    registry=Registry(lambda:settings,{'notes_search':lambda query:{'notes':[NOTE]},'note_read':lambda id:NOTE})
    with tempfile.TemporaryDirectory() as temporary:
        service=WorkflowService(lambda:settings,registry,lambda:model,threading.BoundedSemaphore(1),
            'Use supplied evidence.',root=Path(temporary)/'runs')
        try:
            timings=[];cpu=time.process_time()
            for _ in range(RUNS):
                start=time.perf_counter();run=service.start('Analyze the budget','research');service.thread.join(WAIT_S)
                assert service.detail(run['id'])['status']=='complete'
                timings.append((time.perf_counter()-start)*1000)
            model.delay=BUSY_MODEL_S;run=service.start('Analyze the budget')
            def launch(_):
                try:service.start('Concurrent task');return 'unexpectedly accepted'
                except WorkflowError as error:return error.status
            with ThreadPoolExecutor(max_workers=8) as pool:rejected=list(pool.map(launch,range(CONCURRENT_ATTEMPTS)))
            assert rejected==[429]*CONCURRENT_ATTEMPTS
            service.thread.join(WAIT_S)
            model.delay=1;run=service.start('Cancellation check')
            time.sleep(BUSY_MODEL_S);start=time.perf_counter();service.cancel(run['id']);service.thread.join(WAIT_S)
            cancel_ms=(time.perf_counter()-start)*1000
            assert service.detail(run['id'])['status']=='cancelled'
            print(json.dumps({'synthetic_model':True,'live_model_calls':0,'completed_runs':RUNS,
                'median_ms':statistics.median(timings),'p95_ms':sorted(timings)[int(RUNS*.95)],
                'max_worker_concurrency':model.peak,'busy_rejected':len(rejected),'cancellation_ms':cancel_ms,
                'cpu_s':time.process_time()-cpu,'peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'rss_units':'bytes on macOS; KiB on Linux','sqlite_bytes':sum(p.stat().st_size for p in (Path(temporary)/'runs').glob('*.sqlite'))},indent=2))
        finally:service.close()


if __name__=='__main__':main()
