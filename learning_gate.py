"""Offline evaluated behavior bundles. Serving agents have no promotion tool.

Only bounded text changes can enter a bundle. Enforcers, tests, permissions and
application code are outside this schema. Protected evaluator/reviewer keys must
belong to separate OS identities; the proposer receives neither key nor tests.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time

from execution_control import ControlError,encode,digest

SCHEMA_VERSION=1
MAX_COMPONENT_CHARS=4000
MAX_BUNDLE_SECONDS=30*24*3600
MIN_PROTECTED_CASES=8
PROTECTED_REPETITIONS=3
SUCCESS_FLOOR=.90
GAIN_FLOOR=.10
COST_REDUCTION=.20
ALLOWED_COMPONENTS=frozenset({'instructions','procedure','routing'})
OUTCOME_STATES=frozenset({'success','failure','cancelled','infrastructure_outage','unknown'})
HASH_LENGTH=64
MAX_IDENTIFIER_CHARS=128
MAX_EVIDENCE_HASHES=24
GAIN_EPSILON=1e-9


def valid_hash(value):
    return isinstance(value,str) and len(value)==HASH_LENGTH and all(c in '0123456789abcdef' for c in value)


def signature(key,payload):
    return hmac.new(key.encode(),encode(payload).encode(),hashlib.sha256).hexdigest()


def verify(key,payload,mac):
    if not isinstance(mac,str) or not hmac.compare_digest(signature(key,payload),mac):raise ControlError('Untrusted evaluation or review receipt.')


class LearningStore:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():raise ControlError('Unsafe learning store.')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.path.parent,0o700)
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.fchmod(fd,0o600);os.close(fd)
        self.db=sqlite3.connect(self.path,check_same_thread=False)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS bundles(hash TEXT PRIMARY KEY,data TEXT);
            CREATE TABLE IF NOT EXISTS active(scope TEXT PRIMARY KEY,hash TEXT);
            CREATE TABLE IF NOT EXISTS evaluation_reuse(protected_hash TEXT PRIMARY KEY,candidate_hash TEXT);
            CREATE TABLE IF NOT EXISTS promotions(seq INTEGER PRIMARY KEY,scope TEXT,old_hash TEXT,new_hash TEXT,at REAL);
            CREATE TABLE IF NOT EXISTS outcomes(run_hash TEXT PRIMARY KEY,scope TEXT,data TEXT);
        ''')
        self.lock=threading.RLock()

    def outcome(self,scope,record):
        """Whitelist-only minimized data. No prompt, answer, note, path or audio."""
        fields={'run_hash','status','engine_version','model_version','tool_version','behavior_hash',
                'latency_ms','tokens','usage_complete','cost_microunits','verified','receipt_hashes','source_hashes'}
        if (not isinstance(scope,str) or not scope or not isinstance(record,dict) or set(record)!=fields
                or record['status'] not in OUTCOME_STATES or not valid_hash(record['run_hash'])
                or not valid_hash(record['behavior_hash']) or type(record['verified']) is not bool
                or type(record['usage_complete']) is not bool):raise ControlError('Invalid minimized outcome.')
        for field in ('latency_ms','tokens','cost_microunits'):
            if record[field] is None and field!='latency_ms':continue
            if type(record[field]) is not int or record[field]<0:raise ControlError('Invalid measured outcome.')
        if record['usage_complete'] and record['tokens'] is None:raise ControlError('Missing usage cannot be complete.')
        for field in ('engine_version','model_version','tool_version'):
            value=record[field]
            if not isinstance(value,str) or not value or len(value)>MAX_IDENTIFIER_CHARS or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:=/-' for c in value):
                raise ControlError('Use version identifiers only.')
        for field in ('receipt_hashes','source_hashes'):
            if not isinstance(record[field],list) or len(record[field])>MAX_EVIDENCE_HASHES or not all(valid_hash(x) for x in record[field]):raise ControlError('Use evidence hashes only.')
        if record['status']=='success' and not record['verified']:raise ControlError('Unverified success rejected.')
        with self.lock,self.db:
            old=self.db.execute('SELECT data FROM outcomes WHERE run_hash=?',(record['run_hash'],)).fetchone()
            if old and old[0]!=encode(record):raise ControlError('Conflicting outcome identity.')
            self.db.execute('INSERT OR IGNORE INTO outcomes VALUES (?,?,?)',(record['run_hash'],scope,encode(record)))

    def propose(self,*,scope,parent_hash,components,requirements,evidence,expires_at):
        if (not isinstance(scope,str) or not scope or len(scope)>MAX_IDENTIFIER_CHARS
                or parent_hash is not None and not valid_hash(parent_hash)
                or not isinstance(components,dict) or not components or set(components)-ALLOWED_COMPONENTS
                or any(not isinstance(x,str) or not 0<len(x)<=MAX_COMPONENT_CHARS for x in components.values())
                or not isinstance(requirements,dict) or set(requirements)!={'engine','model','tools'}
                or not all(isinstance(v,str) and 0<len(v)<=MAX_IDENTIFIER_CHARS for v in requirements.values())
                or not isinstance(evidence,list) or not 0<len(evidence)<=MAX_EVIDENCE_HASHES or not all(valid_hash(x) for x in evidence)
                or type(expires_at) not in (int,float) or not time.time()<expires_at<=time.time()+MAX_BUNDLE_SECONDS):
            raise ControlError('Invalid bounded behavior bundle.')
        bundle=dict(schema_version=SCHEMA_VERSION,scope=scope,parent_hash=parent_hash,components=components,
                    requirements=requirements,evidence=evidence,expires_at=expires_at)
        bundle['hash']=digest(bundle)
        with self.lock,self.db:self.db.execute('INSERT OR IGNORE INTO bundles VALUES (?,?)',(bundle['hash'],encode(bundle)))
        return bundle

    def current(self,scope,requirements=None):
        with self.lock:
            row=self.db.execute('SELECT b.data FROM active a JOIN bundles b ON b.hash=a.hash WHERE a.scope=?',(scope,)).fetchone()
            if row is None:return None
            bundle=json.loads(row[0])
            if bundle['expires_at']<=time.time() or requirements is not None and bundle['requirements']!=requirements:return None
            return bundle

    def promote(self,bundle_hash,report,report_mac,*,evaluator_key,review_receipt,review_mac,reviewer_key):
        """Keys are operator/evaluator capabilities, never fields from an agent."""
        verify(evaluator_key,report,report_mac);verify(reviewer_key,review_receipt,review_mac)
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row=self.db.execute('SELECT data FROM bundles WHERE hash=?',(bundle_hash,)).fetchone()
                if row is None:raise ControlError('Unknown candidate.')
                bundle=json.loads(row[0]);scope=bundle['scope']
                unsigned={k:v for k,v in bundle.items() if k!='hash'}
                if digest(unsigned)!=bundle_hash or bundle['expires_at']<=time.time():raise ControlError('Stale or corrupted candidate.')
                current=self.db.execute('SELECT hash FROM active WHERE scope=?',(scope,)).fetchone()
                parent=current[0] if current else None
                if bundle['parent_hash']!=parent:raise ControlError('Tested parent is no longer current.')
                if (review_receipt!={'candidate_hash':bundle_hash,'report_hash':digest(report),'approved':True}
                        or report.get('candidate_hash')!=bundle_hash or report.get('parent_hash')!=parent
                        or report.get('scope')!=scope or report.get('requirements')!=bundle['requirements']):raise ControlError('Review/evaluation scope mismatch.')
                self.validate_report(report)
                if self.db.execute('SELECT 1 FROM evaluation_reuse WHERE protected_hash=?',(report['protected_hash'],)).fetchone():
                    raise ControlError('Protected evaluation was already consumed; require fresh tests.')
                self.db.execute('INSERT INTO evaluation_reuse VALUES (?,?)',(report['protected_hash'],bundle_hash))
                self.db.execute('INSERT OR REPLACE INTO active VALUES (?,?)',(scope,bundle_hash))
                self.db.execute('INSERT INTO promotions(scope,old_hash,new_hash,at) VALUES (?,?,?,?)',(scope,parent,bundle_hash,time.time()))
                self.db.commit()
            except BaseException:self.db.rollback();raise
        return bundle

    @staticmethod
    def validate_report(report):
        required={'candidate_hash','parent_hash','scope','requirements','protected_hash','case_count','repetitions',
            'executions','critical_failures','families','baseline_success','candidate_success','baseline_cost',
            'candidate_cost','total_cost','all_costs_counted','equivalent_budgets','model_backed','complete'}
        if (not isinstance(report,dict) or set(report)!=required or not valid_hash(report['protected_hash'])
                or any(report[k] is not True for k in ('complete','all_costs_counted','equivalent_budgets','model_backed'))
                or type(report['case_count']) is not int or report['case_count']<MIN_PROTECTED_CASES
                or report['repetitions']!=PROTECTED_REPETITIONS
                or report['executions']!=report['case_count']*PROTECTED_REPETITIONS*2
                or report['critical_failures']!=0 or not report['families']):raise ControlError('Incomplete protected validation.')
        for key in ('baseline_success','candidate_success','baseline_cost','candidate_cost','total_cost'):
            if type(report[key]) not in (int,float) or not math.isfinite(report[key]) or report[key]<0:raise ControlError('Invalid evaluation measurement.')
        if not 0<=report['baseline_success']<=1 or not SUCCESS_FLOOR<=report['candidate_success']<=1:raise ControlError('Success floor failed.')
        if report['total_cost']<report['baseline_cost']+report['candidate_cost']:raise ControlError('Evaluation costs incomplete.')
        for values in report['families'].values():
            if (set(values)!={'baseline','candidate','floor'} or not 0<=values['baseline']<=1
                    or not 0<=values['floor']<=1 or not max(values['baseline'],values['floor'],SUCCESS_FLOOR)<=values['candidate']<=1):
                raise ControlError('Task-family regression or floor failure.')
        gain=report['candidate_success']-report['baseline_success']
        cheaper=(report['baseline_cost']>0 and report['candidate_cost']<=report['baseline_cost']*(1-COST_REDUCTION)
                 and report['candidate_success']>=report['baseline_success'])
        if gain+GAIN_EPSILON<GAIN_FLOOR and not cheaper:raise ControlError('Inconclusive; retain incumbent.')

    def rollback(self,scope,*,review_receipt,review_mac,reviewer_key):
        verify(reviewer_key,review_receipt,review_mac)
        with self.lock,self.db:
            current=self.db.execute('SELECT hash FROM active WHERE scope=?',(scope,)).fetchone()
            previous=self.db.execute('SELECT old_hash FROM promotions WHERE scope=? ORDER BY seq DESC LIMIT 1',(scope,)).fetchone()
            if not current or not previous or review_receipt!={'scope':scope,'from_hash':current[0],'to_hash':previous[0],'rollback':True}:
                raise ControlError('Invalid reviewed rollback.')
            if previous[0] is None:self.db.execute('DELETE FROM active WHERE scope=?',(scope,))
            else:self.db.execute('UPDATE active SET hash=? WHERE scope=?',(previous[0],scope))
            self.db.execute('INSERT INTO promotions(scope,old_hash,new_hash,at) VALUES (?,?,?,?)',(scope,current[0],previous[0],time.time()))

    def erase_scope(self,scope):
        """Operator-only deletion of derived local records; backups need retention handling."""
        with self.lock,self.db:
            hashes=[r[0] for r in self.db.execute('SELECT hash FROM bundles WHERE json_extract(data,\'$.scope\')=?',(scope,))]
            for value in hashes:self.db.execute('DELETE FROM evaluation_reuse WHERE candidate_hash=?',(value,))
            self.db.execute('DELETE FROM outcomes WHERE scope=?',(scope,))
            self.db.execute('DELETE FROM active WHERE scope=?',(scope,))
            self.db.execute('DELETE FROM promotions WHERE scope=?',(scope,))
            self.db.execute('DELETE FROM bundles WHERE json_extract(data,\'$.scope\')=?',(scope,))
        with self.lock:self.db.execute('VACUUM')

    def close(self):self.db.close()
