"""Private Linux scheduler supervisor. No HTTP listener; no host capability tools.

The operator writes selected requests into a private spool. UI/controller network
integration remains gated. This process needs a fresh Linux Codex login; it never
imports a Mac authentication cache or reads the original JARVIS config.json.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import secrets
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from execution_adapters import LangGraphAdapter
from execution_control import ControlStore,digest,feature_flags
from execution_scheduler import Scheduler
from outcome_collection import capture_execution
from ultra_tools import Registry
from workflow_runtime import WorkflowService,READ_TOOLS
import build
from codex_bridge import CodexBridge
import note_store
import ultra

RUNTIME_CHECK_TIMEOUT_S=10
SPOOL_POLL_S=.1
MAX_SPOOL_BYTES=8192
MAX_SPOOL_FILES=50
QUARANTINE_ID_BYTES=8
MAX_SEARCH_NOTES=3
MAX_NOTE_CHARS=7000
DISABLED_FEATURES=('shell_tool','exec_policy','apply_patch','web_search','image_generation','multi_agent')


def private_file(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:raise ValueError('Private regular operator file required.')
    return path


def ingest_spool(scheduler,spool,*,duration_s,versions,permissions):
    """Malformed operator files cannot restart/cancel unrelated admitted work."""
    counts={'accepted':0,'rejected':0}
    for request in sorted(Path(spool).glob('*.json'))[:MAX_SPOOL_FILES]:
        try:
            private_file(request)
            if request.stat().st_size>MAX_SPOOL_BYTES:raise ValueError('Spool size limit.')
            data=json.loads(request.read_text())
            if not isinstance(data,dict) or set(data)!={'request_key','conversation_id','project_id','question'}:
                raise ValueError('Invalid spool schema.')
            scheduler.enqueue(question=data['question'],key=data['request_key'],conversation_id=data['conversation_id'],
                project_id=data['project_id'],engine='langgraph',permissions=permissions,duration_s=duration_s,
                versions=versions,options={'workflow':'research'})
        except Exception:
            # Rename the directory entry, never follow a rejected symlink. Keep
            # its contents private for operator inspection, with no log payload.
            suffix='.rejected-'+secrets.token_hex(QUARANTINE_ID_BYTES)
            try:request.rename(request.with_suffix(suffix))
            except OSError:pass
            counts['rejected']+=1
        else:
            # Admission and payload are durable before the source is marked.
            # A crash before rename simply deduplicates on the next poll.
            try:request.rename(request.with_suffix('.accepted-'+secrets.token_hex(QUARANTINE_ID_BYTES)))
            except OSError:pass
            counts['accepted']+=1
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    config=json.loads(private_file(args.config).read_text())
    if sys.platform!='linux' and not args.check:raise SystemExit('Remote controller requires Linux validation.')
    if args.check:
        print('Controller configuration parsed; deployment/model gates remain unverified.');return
    if config.get('linux_model_gate_passed') is not True:raise SystemExit('Linux/model acceptance gate is not recorded.')
    runtime=Path(config['state_dir']);runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    flags=feature_flags(config['flags_file'])
    if flags['deepagents'] or flags['remote_workspaces'] or flags['learning_promotion']:
        raise SystemExit('These integrations remain gated; this supervisor supports the existing executor only.')
    executable=shutil.which('codex')
    if not executable:raise SystemExit('Install and freshly log into the pinned Linux Codex runtime privately.')
    version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=RUNTIME_CHECK_TIMEOUT_S)
    if version.returncode or version.stdout.strip()!=config['codex_runtime_version']:
        raise SystemExit('Linux model runtime differs from its recorded version.')
    if subprocess.run([executable,'login','status'],capture_output=True,timeout=RUNTIME_CHECK_TIMEOUT_S).returncode:
        raise SystemExit('Complete a fresh private Linux login before running tasks.')
    if not {config['quick_model'],config['brain_model']} <= ultra.VERIFIED_MODELS:
        raise SystemExit('Configured models require separate compatibility validation.')
    settings=replace(ultra.Settings(),enabled=True,tools_enabled=True,workflows_enabled=True,terminal_monitor_enabled=False,
        quick_model=config['quick_model'],brain_model=config['brain_model'])
    vault=Path(config['approved_notes_dir']).resolve()
    notes=build.read_notes(vault)
    def read(id):
        note=next(n for n in notes if n['id']==id)
        result=note_store.read(note,vault);result['text']=result['text'][:MAX_NOTE_CHARS];return result
    def search(query):
        terms=set(query.lower().split())
        ranked=sorted(notes,key=lambda n:sum(word in n['text'].lower() for word in terms),reverse=True)
        return {'notes':[read(n['id']) for n in ranked[:MAX_SEARCH_NOTES]]}
    registry=Registry(lambda:settings,{'notes_search':search,'note_read':read})
    service=WorkflowService(lambda:settings,registry,lambda:CodexBridge(executable,DISABLED_FEATURES),
        threading.BoundedSemaphore(1),'Answer using only approved source evidence. ',root=runtime/'workflows')
    store=ControlStore(runtime/'control.sqlite')
    scheduler=Scheduler(store,{'langgraph':lambda run:LangGraphAdapter(service)},
        outcome_hook=lambda run,status:capture_execution(run,status,flags_path=config['flags_file'],store_path=runtime/'learning.sqlite'))
    scheduler.recover()
    spool=runtime/'spool';spool.mkdir(mode=0o700,exist_ok=True)
    stop=threading.Event()
    for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,lambda *_:stop.set())
    try:
        while not stop.is_set():
            ingest_spool(scheduler,spool,duration_s=settings.request_timeout_s,permissions=READ_TOOLS,
                versions={'engine':config['codex_runtime_version'],'model':settings.quick_model+'/'+settings.brain_model,
                    'tools':digest(registry.catalog()),'behavior':'incumbent-v1'})
            scheduler.tick();stop.wait(SPOOL_POLL_S)
    finally:
        if scheduler.active:
            try:scheduler.cancel(scheduler.active)
            except Exception:pass
        service.close();store.close()


if __name__=='__main__':main()
