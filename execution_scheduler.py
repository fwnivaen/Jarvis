"""Durable single-owner scheduler; runs independently of viewer connections.

Adapter factories are trusted controller configuration, not prompt-selected code.
Restarted in-flight jobs become interrupted and require explicit recovery. No
automatic replay of uncertain work or expansion of concurrency.
"""
import json
import threading
import time

from execution_control import ControlError,encode,TERMINAL

POLL_S=.1
MAX_QUESTION_CHARS=2000


class Scheduler:
    def __init__(self,store,factories,outcome_hook=None):
        self.store,self.factories=store,dict(factories)
        self.active=None
        self.adapter=None
        self.lock=threading.RLock()
        self.outcome_hook=outcome_hook
        with store.db:
            store.db.execute('CREATE TABLE IF NOT EXISTS jobs(run_id TEXT PRIMARY KEY, data TEXT)')
            store.db.execute('CREATE TABLE IF NOT EXISTS job_results(run_id TEXT PRIMARY KEY, data TEXT)')
            store.db.execute('CREATE TABLE IF NOT EXISTS collection_status(run_id TEXT PRIMARY KEY, status TEXT)')

    def enqueue(self,key,question,*,engine,conversation_id,project_id,versions,permissions,duration_s,options=None):
        if engine not in self.factories or not isinstance(question,str) or not 0<len(question)<=MAX_QUESTION_CHARS:
            raise ControlError('Unsupported executor or invalid task.')
        job={'question':question,'engine':engine,'options':options or {}}
        # Include workload hash in the deduplication fingerprint; same key cannot
        # be reused to change a question or options under an old admission.
        versions=dict(versions,workload=__import__('execution_control').digest(job))
        run,created=self.store.admit(key,conversation_id=conversation_id,project_id=project_id,engine=engine,
            versions=versions,permissions=permissions,duration_s=duration_s)
        with self.store.lock,self.store.db:
            old=self.store.db.execute('SELECT data FROM jobs WHERE run_id=?',(run['id'],)).fetchone()
            if old and old[0]!=encode(job):raise ControlError('Conflicting durable workload.')
            self.store.db.execute('INSERT OR IGNORE INTO jobs VALUES (?,?)',(run['id'],encode(job)))
        return run,created

    def recover(self):
        with self.lock:
            if self.active:raise ControlError('Cannot recover while adapter active.')
            return self.store.recover()

    def tick(self):
        with self.lock:
            if self.active:
                status=self.adapter.status()
                if status['status'] not in TERMINAL or not status.get('settled',False):return status
                run=self.store.get(self.active)
                terminal=status['status']
                if run['status']=='cancelling':terminal='cancelled'
                if terminal=='complete' and status.get('result') is None:terminal='failed'
                if terminal=='complete':
                    with self.store.lock,self.store.db:
                        self.store.db.execute('INSERT OR REPLACE INTO job_results VALUES (?,?)',(self.active,encode(status['result'])))
                final=self.store.transition(self.active,terminal)
                collection='not_configured'
                if self.outcome_hook:
                    try:
                        collection=self.outcome_hook(final,status)
                        if collection not in {'off','stored'}:collection='unavailable'
                    except Exception:collection='unavailable'  # Never block delivery.
                with self.store.lock,self.store.db:
                    self.store.db.execute('INSERT OR REPLACE INTO collection_status VALUES (?,?)',(self.active,collection))
                self.active=self.adapter=None
                return status
            with self.store.lock:
                rows=[json.loads(r[0]) for r in self.store.db.execute('SELECT data FROM runs')]
                queued=sorted((r for r in rows if r['status']=='queued'),key=lambda r:r['created_at'])
                if not queued:return None
                run=queued[0]
                jobrow=self.store.db.execute('SELECT data FROM jobs WHERE run_id=?',(run['id'],)).fetchone()
            if jobrow is None:
                # Admission-before-payload crash: no task can be fabricated.
                self.store.transition(run['id'],'interrupted');return None
            if run['expires_at']<=time.time():
                self.store.transition(run['id'],'interrupted');return None
            self.store.transition(run['id'],'running')
            self.active=run['id']
            try:
                self.adapter=self.factories[run['engine']](self.store.get(run['id']))
                return self.adapter.start(question=json.loads(jobrow[0])['question'],**json.loads(jobrow[0])['options'])
            except Exception:
                # A failing start may have started underlying work: retain owner
                # until its actual settlement; issue Stop when supported.
                if self.adapter is not None:
                    try:self.adapter.cancel()
                    except Exception:pass
                    if not self.adapter.status().get('settled',False):return self.adapter.status()
                self.store.transition(run['id'],'failed')
                self.active=self.adapter=None
                raise ControlError('Executor start failed; inspect durable state.') from None

    def cancel(self,run_id):
        with self.lock:
            run=self.store.get(run_id)
            if run['status']=='queued':return self.store.transition(run_id,'cancelled')
            if run_id!=self.active:raise ControlError('Task not owned by this scheduler.')
            if run['status']!='cancelling':self.store.transition(run_id,'cancelling')
            self.adapter.cancel()
            return self.store.get(run_id)

    def serve(self,stop):
        while not stop.is_set():
            self.tick();stop.wait(POLL_S)
