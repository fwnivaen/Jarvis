"""Local durable workflow service. Graph scheduling belongs to LangGraph.

Only bounded, read-only analysis tools are offered here. Existing chat retains
its original tools. No hosted tracing, arbitrary graph/config uploads or pickle.
"""
import json
import hashlib
import os
import queue
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from codex_bridge import BridgeError
from ultra_tools import ToolSession
from ultra import CHECKED_SCHEMA, REPORT_SCHEMA, STAGE_ONE_BOUNDARY, TOOLS_BOUNDARY, checked, checked_report, decode
from ultra_workflows import workflow_template
from workflow_graph import compile_workflow, GRAPH_RECURSION_LIMIT

ROOT = Path(__file__).resolve().parent / '.local' / 'graph-workflows'
MAX_RUNS = 50
MAX_DB_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 256
MAX_QUESTION_CHARS = 2000
MAX_TEXT_CHARS = 8000
MAX_TASK_CHARS = 900
MAX_WORKERS = 3
MAX_RESTARTS = 2
MAX_TOOL_CALLS = 24
SQL_TIMEOUT_S = 5
TOOL_POLL_S = 0.1
STREAM_WAIT_S = 1
STREAM_CONNECTION_S = 20
MAX_STREAMS = 4
SECONDS_DIGITS = 3
ID_BYTES = 12
READ_TOOLS = frozenset({'notes_search', 'note_read', 'preferences_get'})
LEGACY_TOOL_BOUNDARY = 'Never use tools, execute commands, inspect files, edit files, or browse the network.'
ANALYSIS_TOOL_BOUNDARY = 'Only registered read-only Jarvis tools may be used. No shell, arbitrary files, writes or browsing.'
REVIEW_BOUNDARY = STAGE_ONE_BOUNDARY.replace(
    'Stage 1 is read-only: no tools, file changes, sends, screen actions or test execution are available.',
    'This final review cannot call tools. Earlier workflow phases have already executed the confirmed_tool_calls in the payload.').replace(
    'Never claim these actions were performed.',
    'You may accurately report those confirmed operations. Do not claim unconfirmed actions.')
TERMINAL = frozenset({'complete', 'failed', 'cancelled', 'interrupted'})
RETRYABLE = frozenset({'invalid_output', 'missing_sources', 'math_check', 'disconnected', 'unavailable', 'protocol_failure'})
SAFE_FAILURES = RETRYABLE | {'timeout', 'cancelled', 'budget_exhausted', 'tool_failed', 'inference_failed',
    'model_unavailable', 'effort_unavailable', 'model_mismatch', 'blocked_action', 'storage_unavailable', 'source_changed'}
WORKFLOW_LABELS = {'general': 'Focused answer', 'research': 'Evidence research', 'document': 'Document analysis', 'code': 'Code review'}
WORKER_COUNTS = {'general': 1, 'research': 3, 'document': 2, 'code': 2}
EVENT_KINDS = frozenset({'started', 'resumed', 'node_complete', 'agent_started', 'agent_complete',
    'agent_failed', 'tool_started', 'tool_complete', 'tool_failed', 'usage', 'complete', 'failed',
    'cancel_requested', 'cancelled', 'interrupted'})
RUN_ID = re.compile(r'[a-f0-9]{24}\Z')
SECRET_PATTERNS = (
    re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{8,}|gh[pousr]_[a-z0-9_]{8,}|github_pat_[a-z0-9_]{8,})'),
    re.compile(r'(?i)\b(?:api[_ -]?key|authorization|password|secret|access[_ -]?token)\s*[:=]\s*["\']?[^\s,;"\']+'),
    re.compile(r'(?i)\bbearer\s+[a-z0-9._~+/-]+=*'),
    re.compile(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----'),
)


class WorkflowError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


class Redactor:
    def __init__(self, values=()):
        self.values = tuple(value for value in values if isinstance(value, str) and len(value) >= 8)

    def text(self, value, limit=MAX_TEXT_CHARS):
        text = str(value)
        for value in self.values:
            text = text.replace(value, '[redacted]')
        for pattern in SECRET_PATTERNS:
            text = pattern.sub('[redacted]', text)
        return text[:limit]


class RunStore:
    """Small private catalog/event journal; graph state uses SqliteSaver separately."""
    def __init__(self, root=ROOT):
        self.root = Path(root)
        if self.root.is_symlink():
            raise OSError('Unsafe workflow directory')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.lock = threading.RLock()
        self.path = self.root / 'catalog.sqlite'
        self.conn = self.connect(self.path)
        with self.conn:
            self.conn.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            self.conn.execute('CREATE TABLE IF NOT EXISTS admissions (request_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, run_id TEXT NOT NULL)')

    @staticmethod
    def connect(path):
        if path.is_symlink():
            raise OSError('Unsafe database path')
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        conn = sqlite3.connect(path, timeout=SQL_TIMEOUT_S, check_same_thread=False)
        # DELETE mode avoids world-readable WAL sidecars; parent is private too.
        conn.execute('PRAGMA journal_mode=DELETE')
        return conn

    def get(self, identifier):
        if not isinstance(identifier, str) or not RUN_ID.fullmatch(identifier):
            raise WorkflowError('Unknown workflow run.', 404)
        with self.lock:
            row = self.conn.execute('SELECT data FROM runs WHERE id=?', (identifier,)).fetchone()
            if row is None:
                raise WorkflowError('Unknown workflow run.', 404)
            return json.loads(row[0])

    def save(self, data):
        with self.lock, self.conn:
            self.conn.execute('INSERT OR REPLACE INTO runs VALUES (?, ?)',
                (data['id'], json.dumps(data, allow_nan=False)))

    def admitted(self, request_key, fingerprint):
        if request_key is None:
            return None
        if not isinstance(request_key, str) or not RUN_ID.fullmatch(request_key):
            raise WorkflowError('Invalid workflow request key.')
        with self.lock:
            row = self.conn.execute('SELECT fingerprint,run_id FROM admissions WHERE request_key=?', (request_key,)).fetchone()
            if row is None:
                return None
            if row[0] != fingerprint:
                raise WorkflowError('That request key belongs to a different task.', 409)
            return self.get(row[1])

    def admit(self, data, request_key, fingerprint):
        with self.lock, self.conn:
            self.conn.execute('INSERT INTO runs VALUES (?,?)', (data['id'], json.dumps(data, allow_nan=False)))
            if request_key is not None:
                self.conn.execute('INSERT INTO admissions VALUES (?,?,?)', (request_key, fingerprint, data['id']))

    def all(self):
        with self.lock:
            return sorted([json.loads(row[0]) for row in self.conn.execute('SELECT data FROM runs')],
                key=lambda row: row['created_at'], reverse=True)

    def capacity(self):
        return len(self.all()) < MAX_RUNS and sum(p.stat().st_size for p in self.root.glob('*.sqlite')) < MAX_DB_BYTES

    def close(self):
        self.conn.close()


class GraphJobs:
    """Adapt JARVIS's real model, validators and registered tools to graph nodes."""
    def __init__(self, service, run_id, bridge, cancel):
        self.service, self.run_id, self.bridge, self.cancel = service, run_id, bridge, cancel
        self.settings = service.settings()
        self.session = ToolSession(service.tools, run_id, root=service.root / "tool-journals",
            permissions=READ_TOOLS, cancel=cancel)

    def guard(self):
        if self.cancel.is_set():
            raise BridgeError('cancelled')
        run = self.service.store.get(self.run_id)
        if time.time() >= run['expires_at']:
            raise BridgeError('budget_exhausted')
        return run

    def retrieve(self, state):
        self.guard()
        self.service.phase(self.run_id, 'retrieve')
        # Real registered tool execution, visible even when a model needs no tools.
        notes = self.tool('notes_search', {'query': state['question']}, 'retriever')['notes']
        return {'notes': notes}

    def assign(self, state):
        self.guard()
        self.service.phase(self.run_id, 'assign')
        recipe = workflow_template(workflow=state['workflow'])
        count = min(WORKER_COUNTS[state['workflow']], self.settings.max_workers, MAX_WORKERS)
        tasks = [role['name'] + ': ' + role['assignment'] for role in recipe['roles'][:count]]
        self.service.change(self.run_id, tasks=tasks)
        return {'tasks': tasks}

    def tool(self, name, arguments, slot, deadline=None):
        run = self.guard()
        deadline = min(deadline or float('inf'), time.monotonic() + max(0, run['expires_at'] - time.time()))
        if name not in READ_TOOLS:
            raise BridgeError('blocked_action')
        with self.service.lock:
            run = self.service.store.get(self.run_id)
            if run['tool_calls'] >= MAX_TOOL_CALLS:
                raise BridgeError('budget_exhausted')
            run['tool_calls'] += 1
            self.service.store.save(run)
        self.service.event(self.run_id, 'tool_started', slot=slot, tool=name)
        delivered = queue.Queue(maxsize=1)
        if not self.service.tool_slots.acquire(blocking=False):
            self.service.event(self.run_id, 'tool_failed', slot=slot, tool=name)
            raise BridgeError('tool_failed')
        with self.service.lock:
            self.service.pending_tools[self.run_id] = self.service.pending_tools.get(self.run_id, 0) + 1
        def execute():
            try:
                delivered.put((True, self.session.call(name, arguments, deadline)))
            except Exception:
                delivered.put((False, None))
            finally:
                self.service.tool_slots.release()
                with self.service.lock:
                    self.service.pending_tools[self.run_id] -= 1
                    if not self.service.pending_tools[self.run_id]:
                        try:
                            saved = self.service.store.get(self.run_id)
                            if saved['status'] in TERMINAL:
                                self.service.change(self.run_id, cleanup='complete')
                                self.service.release_owner(self.run_id)
                        except (sqlite3.Error, WorkflowError):
                            pass
        threading.Thread(target=execute, daemon=True, name='jarvis-read-tool').start()
        try:
            while True:
                self.guard()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BridgeError('timeout')
                try:
                    success, result = delivered.get(timeout=min(remaining, TOOL_POLL_S))
                    break
                except queue.Empty:
                    continue
            if not success:
                raise BridgeError('tool_failed')
            self.guard()
        except Exception as error:
            self.service.event(self.run_id, 'tool_failed', slot=slot, tool=name)
            raise BridgeError(getattr(error, 'code', 'tool_failed')) from None
        self.service.event(self.run_id, 'tool_complete', slot=slot, tool=name)
        return result

    def invoke(self, slot, assignment, payload, schema, validator, model, tools=False):
        while True:
            run = self.guard()
            with self.service.lock:
                run = self.service.store.get(self.run_id)
                row = run['agents'].get(slot, {'slot': slot, 'task': assignment, 'attempts': 0,
                    'started_at': time.time(), 'expires_at': min(run['expires_at'], time.time() +
                    (self.settings.request_timeout_s if slot == 'reviewer' else self.settings.worker_timeout_s)),
                    'tokens': 0, 'usage_reported': False, 'model': model, 'effort': self.settings.effort})
                if row['attempts'] > self.settings.worker_retries or time.time() >= row['expires_at']:
                    raise BridgeError('budget_exhausted')
                row.update(attempts=row['attempts'] + 1, status='running', error=None)
                row.pop('ended_at', None)
                run['agents'][slot] = row
                self.service.store.save(run)  # Reserve attempt BEFORE external inference.
            self.service.event(self.run_id, 'agent_started', slot=slot)
            deadline = time.monotonic() + max(0, min(row['expires_at'], run['expires_at']) - time.time())
            usage = {}
            def observer(values):
                usage.update(values)
                self.service.agent(self.run_id, slot, current_tokens=usage.get('totalTokens'))
                self.service.event(self.run_id, 'usage', slot=slot)
            options = {}
            sources = list(payload['notes'])
            confirmed_tools = []
            if tools:
                specs = [item for item in self.service.tools.dynamic_specs() if item['name'] in READ_TOOLS]
                def handle(name, arguments, tool_deadline):
                    result = self.tool(name, arguments, slot, tool_deadline)
                    confirmed_tools.append(name)
                    discovered = result.get('notes', []) if isinstance(result, dict) else []
                    if isinstance(result, dict) and 'id' in result and 'text' in result:
                        discovered = discovered + [result]
                    for note in discovered:
                        if type(note.get('id')) is int and isinstance(note.get('text'), str):
                            prior = next((n for n in sources if n['id'] == note['id']), None)
                            if prior is None:
                                sources.append(note)
                            else:
                                if prior.get('revision') != note.get('revision'):
                                    raise BridgeError('source_changed')
                                sources[sources.index(prior)] = dict(prior, **note)
                    return result
                options.update(tools=specs, tool_handler=handle)
            try:
                raw = self.bridge.complete(model=model, effort=self.settings.effort,
                    system=self.service.system.replace(LEGACY_TOOL_BOUNDARY, ANALYSIS_TOOL_BOUNDARY)
                        + (TOOLS_BOUNDARY if tools else REVIEW_BOUNDARY)
                        + ' Perform the assigned task. Return concise supported findings, never private reasoning.',
                    payload=dict(payload, assignment=assignment), schema=schema,
                    deadline=deadline, observer=observer, cancel_event=self.cancel, **options)
                self.guard()
                decoded = decode(raw)
                validator(decoded, sources)
                self.service.agent(self.run_id, slot, status='complete', output=decoded['answer'], ended_at=time.time())
                self.service.event(self.run_id, 'agent_complete', slot=slot)
                return dict(decoded, _sources=sources, _tools=confirmed_tools)
            except Exception as error:
                code = getattr(error, 'code', 'inference_failed')
                code = code if code in SAFE_FAILURES else 'inference_failed'
                self.service.agent(self.run_id, slot, status='cancelled' if self.cancel.is_set() else 'failed',
                    error=code, ended_at=time.time())
                self.service.event(self.run_id, 'agent_failed', slot=slot, error=code)
                if code not in RETRYABLE or row['attempts'] > self.settings.worker_retries:
                    raise BridgeError(code) from None
            finally:
                self.service.add_usage(self.run_id, slot, usage)

    def worker(self, state):
        self.guard()
        self.service.phase(self.run_id, 'workers')
        slot = 'worker-' + str(state['index'] + 1)
        report = self.invoke(slot, state['task'], {'question': state['question'], 'notes': state['notes']},
            REPORT_SCHEMA, checked_report, self.settings.quick_model, tools=True)
        return {'reports': {slot: report}}

    def review(self, state):
        self.guard()
        self.service.phase(self.run_id, 'review')
        sources = {note['id']: note for note in state['notes']}
        reports = []
        confirmed_tools = []
        for slot, report in sorted(state['reports'].items()):
            sources.update({note['id']: note for note in report['_sources']})
            reports.append({key: value for key, value in report.items() if not key.startswith('_')})
            confirmed_tools.extend({'agent': slot, 'tool': name} for name in report.get('_tools', []))
        result = self.invoke('reviewer', 'Check the findings against the sources and arithmetic; answer the original request. '
            'Disclose unresolved issues. Do not repeat completed tools.',
            {'question': state['question'], 'notes': list(sources.values()), 'worker_results': reports,
                'confirmed_tool_calls': confirmed_tools},
            CHECKED_SCHEMA, checked, self.settings.brain_model)
        final = {key: result[key] for key in CHECKED_SCHEMA['required']}
        final['source_refs'] = [{'stable_id': sources[node]['stable_id'], 'revision': sources[node]['revision'],
            'original_id': node} for node in final['nodes'] if sources[node].get('stable_id') and sources[node].get('revision')]
        return {'result': final}


class WorkflowService:
    def __init__(self, settings, tools, bridge_factory, slots, system, root=ROOT, redactor=None):
        self.settings, self.tools, self.bridge_factory, self.slots, self.system = settings, tools, bridge_factory, slots, system
        self.root, self.redactor = Path(root), redactor or Redactor()
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.stream_slots = threading.BoundedSemaphore(MAX_STREAMS)
        self.tool_slots = threading.BoundedSemaphore(MAX_WORKERS)
        self.pending_tools = {}
        self.finished_executors = set()
        self.store = None
        self.bridge = None
        self.active = None
        self.thread = None
        self.cancel_event = None
        self.unavailable = None
        self.source_resolver = None

    def initialize(self):
        with self.lock:
            if self.store is not None:
                return
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: F401
                self.store = RunStore(self.root)
                for run in self.store.all():
                    if run['status'] in ('running', 'cancelling'):
                        run.update(status='interrupted', error='disconnected')
                        for row in run['agents'].values():
                            if row['status'] == 'running':
                                row.update(status='interrupted', error='disconnected', ended_at=time.time())
                        self.store.save(run)
                        self.event(run['id'], 'interrupted')
                self.unavailable = None
            except ImportError:
                self.unavailable = 'Install the workflow dependencies with python3 tools/setup_ultra.py --no-model.'
            except (OSError, sqlite3.Error):
                self.unavailable = 'The private workflow store is unavailable.'

    def enabled(self):
        settings = self.settings()
        return settings.enabled and settings.workflows_enabled and settings.tools_enabled

    def change(self, run_id, **values):
        with self.lock:
            run = self.store.get(run_id)
            run.update(values)
            self.store.save(run)
            self.condition.notify_all()

    def release_owner(self, run_id):
        # Cancellation fences delivery promptly, but the shared admission slot
        # belongs to the run until BOTH graph and underlying callbacks settle.
        with self.lock:
            if (run_id == self.active and run_id in self.finished_executors
                    and not self.pending_tools.get(run_id, 0)):
                self.active = None
                self.finished_executors.discard(run_id)
                self.slots.release()
                self.condition.notify_all()

    def phase(self, run_id, phase):
        self.change(run_id, phase=phase)

    def agent(self, run_id, slot, **values):
        with self.lock:
            run = self.store.get(run_id)
            run['agents'][slot].update(values)
            self.store.save(run)

    def add_usage(self, run_id, slot, usage):
        with self.lock:
            run = self.store.get(run_id)
            row = run['agents'][slot]
            if 'totalTokens' in usage:
                row['tokens'] += usage['totalTokens']
                row['usage_reported'] = True
            else:
                row['unreported_attempts'] = row.get('unreported_attempts', 0) + 1
            row['current_tokens'] = None
            self.store.save(run)

    def event(self, run_id, kind, **values):
        if kind not in EVENT_KINDS or set(values) - {'slot', 'tool', 'node', 'error'}:
            raise ValueError('Non-public activity event')
        with self.lock:
            run = self.store.get(run_id)
            run['sequence'] += 1
            event = dict(id=run['sequence'], kind=kind, elapsed_s=round(time.time()-run['created_at'], SECONDS_DIGITS), **values)
            run['events'] = (run['events'] + [event])[-MAX_EVENTS:]
            self.store.save(run)
            self.condition.notify_all()

    def public(self, run):
        now = time.time()
        rows = []
        for row in run['agents'].values():
            rows.append({key: self.redactor.text(row[key], MAX_TASK_CHARS if key == 'task' else MAX_TEXT_CHARS)
                if key in ('task', 'output') else row[key] for key in
                ('slot', 'task', 'model', 'effort', 'status', 'attempts', 'tokens', 'usage_reported', 'unreported_attempts', 'current_tokens', 'output', 'error') if key in row})
            rows[-1]['elapsed_s'] = round(max(0, row.get('ended_at', now) - row['started_at']), SECONDS_DIGITS)
        result = run.get('result')
        resolved_nodes = result['nodes'] if result else []
        source_refs = result.get('source_refs', []) if result else []
        if source_refs:
            resolved_nodes = []
            for ref in source_refs:
                current = self.source_resolver(ref['stable_id']) if self.source_resolver else None
                if current and current['revision'] == ref['revision']:
                    resolved_nodes.append(current['id'])
        return {'id': run['id'], 'workflow': run['workflow'], 'question': self.redactor.text(run['question'], MAX_QUESTION_CHARS),
            'status': run['status'], 'phase': run['phase'], 'cleanup': run.get('cleanup', 'none'),
            'capabilities': {'cancel': True, 'resume': True, 'pause': False, 'watch': False}, 'error': run.get('error'), 'created_at': run['created_at'],
            'elapsed_s': round(max(0, run.get('ended_at', now)-run['created_at']), SECONDS_DIGITS),
            'remaining_s': round(max(0, run['expires_at']-now), SECONDS_DIGITS), 'agents': rows,
            'tasks': [self.redactor.text(task, MAX_TASK_CHARS) for task in run['tasks']], 'tool_calls': run['tool_calls'],
            'total_tokens': sum(row['tokens'] for row in rows) if any(row['usage_reported'] for row in rows) else None,
            'usage_complete': bool(rows) and all(row['usage_reported'] and not row.get('unreported_attempts') for row in rows),
            'sequence': run['sequence'], 'events': run['events'], 'restarts': run['restarts'],
            'can_retry': run['status'] in ('failed', 'cancelled', 'interrupted') and now < run['expires_at']
                and run['restarts'] < MAX_RESTARTS and not self.active
                and all(row['status'] == 'complete' or
                    (row['attempts'] <= self.settings().worker_retries and row['expires_at'] > now)
                    for row in run['agents'].values())
                and run.get('error') != 'source_changed' and run.get('cleanup') != 'pending',
            'result': {'answer': self.redactor.text(result['answer']), 'nodes': resolved_nodes,
                'source_refs': source_refs, 'sources_changed': bool(source_refs and len(resolved_nodes) != len(source_refs)),
                'about_notes': result['about_notes']} if result else None}

    def catalog(self):
        if self.enabled():
            self.initialize()
        with self.lock:
            return {'enabled': self.enabled(), 'available': self.store is not None, 'notice': self.unavailable,
                'engine': 'LangGraph', 'active': self.active,
                'capabilities': {'cancel': True, 'resume': True, 'pause': False, 'watch': False},
                'limits': {'concurrent_runs': 1, 'max_workers': min(MAX_WORKERS, self.settings().max_workers),
                    'request_timeout_s': self.settings().request_timeout_s, 'max_runs': MAX_RUNS},
                'workflows': [{'id': key, 'label': value} for key, value in WORKFLOW_LABELS.items()],
                'runs': [self.public(run) for run in self.store.all()] if self.store else []}

    def detail(self, run_id):
        self.initialize()
        if self.store is None:
            raise WorkflowError(self.unavailable, 503)
        return self.public(self.store.get(run_id))

    def start(self, question=None, workflow='research', resume=None, request_key=None):
        if not self.enabled():
            raise WorkflowError('Enable Ultra workflows and tools before launching a workflow.', 409)
        self.initialize()
        if self.store is None:
            raise WorkflowError(self.unavailable, 503)
        with self.lock:
            if resume is None:
                if (not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS
                        or not isinstance(workflow, str) or workflow not in WORKFLOW_LABELS):
                    raise WorkflowError('Supply a short question and a known workflow.')
                fingerprint = hashlib.sha256(json.dumps([question.strip(), workflow]).encode()).hexdigest()
                existing = self.store.admitted(request_key, fingerprint)
                if existing:
                    return self.public(existing)
            elif request_key is not None:
                raise WorkflowError('Resume uses its existing run identity.')
            if self.active or not self.slots.acquire(blocking=False):
                raise WorkflowError('JARVIS is already working. Wait or cancel the active workflow.', 429)
            try:
                if resume is not None:
                    run = self.store.get(resume)
                    if not self.public(run)['can_retry']:
                        raise WorkflowError('This run cannot resume within its original budget. Start a new workflow.', 409)
                    if run['settings'] != self.settings().__dict__:
                        raise WorkflowError('Settings changed. Start a new workflow.', 409)
                    run.update(status='running', error=None, restarts=run['restarts']+1)
                    run.pop('ended_at', None)
                else:
                    if not self.store.capacity():
                        raise WorkflowError('Workflow storage is full. Archive the private workflow store while JARVIS is stopped.', 409)
                    now = time.time()
                    run = {'id': secrets.token_hex(ID_BYTES), 'question': question.strip(), 'workflow': workflow,
                        'created_at': now, 'expires_at': now + self.settings().request_timeout_s,
                        'settings': self.settings().__dict__, 'status': 'running', 'phase': 'retrieve', 'tasks': [],
                        'agents': {}, 'events': [], 'sequence': 0, 'restarts': 0, 'tool_calls': 0, 'cleanup': 'none',
                        'versions': {'engine': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            'tools': hashlib.sha256(json.dumps(self.tools.catalog(),sort_keys=True).encode()).hexdigest(),
                            'behavior': hashlib.sha256(self.system.encode()).hexdigest()}}
                if resume is None:
                    self.store.admit(run, request_key, fingerprint)
                else:
                    self.store.save(run)
                self.active, self.cancel_event = run['id'], threading.Event()
                self.thread = threading.Thread(target=self._execute, args=(run['id'], resume is not None), daemon=True,
                    name='jarvis-langgraph')
                self.thread.start()
                return self.public(run)
            except BaseException:
                self.active = None
                self.slots.release()
                raise

    def _execute(self, run_id, resume):
        conn = None
        jobs = None
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            # LangGraph/LangChain honor explicit tracing_context(enabled=False), even
            # if a user's shell has LANGSMITH_TRACING set. Never enable cloud traces.
            from langsmith import tracing_context
            conn = RunStore.connect(self.root / (run_id + '.sqlite'))
            if self.bridge is None:
                self.bridge = self.bridge_factory()
            jobs = GraphJobs(self, run_id, self.bridge, self.cancel_event)
            graph = compile_workflow(jobs, SqliteSaver(conn, serde=JsonPlusSerializer(
                pickle_fallback=False, allowed_json_modules=(), allowed_msgpack_modules=())))
            config = {'configurable': {'thread_id': run_id}, 'max_concurrency': min(MAX_WORKERS, self.settings().max_workers),
                'recursion_limit': GRAPH_RECURSION_LIMIT, 'callbacks': []}
            run = self.store.get(run_id)
            if resume:
                saved = graph.get_state(config)
                # Reject stale evidence. Re-reading is bounded and read-only.
                saved_notes = {note['id']: note for note in saved.values.get('notes', [])}
                for report in saved.values.get('reports', {}).values():
                    saved_notes.update({note['id']: note for note in report.get('_sources', [])})
                for note in saved_notes.values():
                    if note.get('stable_id') and self.source_resolver:
                        resolved = self.source_resolver(note['stable_id'])
                        if not resolved or resolved['id'] != note['id']:
                            raise BridgeError('source_changed')
                    current = jobs.tool('note_read', {'id': note['id']}, 'recovery')
                    if note.get('revision') != current.get('revision'):
                        raise BridgeError('source_changed')
            self.event(run_id, 'resumed' if resume else 'started')
            state = None if resume else {'question': run['question'], 'workflow': run['workflow'], 'reports': {}}
            with tracing_context(enabled=False):
                for update in graph.stream(state, config, stream_mode='updates', durability='sync'):
                    for node in update:
                        if node in ('retrieve', 'assign', 'worker', 'review'):
                            self.event(run_id, 'node_complete', node=node)
                jobs.guard()
                result = graph.get_state(config).values['result']
            self.change(run_id, status='complete', phase='complete', result=result, ended_at=time.time(), error=None)
            self.event(run_id, 'complete')
        except Exception as error:
            code = getattr(error, 'code', 'storage_unavailable' if isinstance(error, (OSError, sqlite3.Error)) else 'inference_failed')
            code = code if code in SAFE_FAILURES else 'inference_failed'
            status = 'cancelled' if self.cancel_event.is_set() else 'failed'
            self.change(run_id, status=status, error=code, ended_at=time.time())
            self.event(run_id, status)
        finally:
            if conn is not None:
                conn.close()
            with self.lock:
                self.change(run_id, cleanup='pending' if self.pending_tools.get(run_id, 0) else 'complete')
                if jobs is not None:
                    jobs.session.close()
                self.finished_executors.add(run_id)
                self.release_owner(run_id)
                try:
                    from outcome_collection import capture
                    self.change(run_id, outcome_collection=capture(self.store.get(run_id)))
                except Exception:
                    self.change(run_id, outcome_collection='unavailable')

    def cancel(self, run_id):
        with self.lock:
            if run_id != self.active:
                raise WorkflowError('That workflow is no longer running.', 409)
            self.cancel_event.set()
            self.change(run_id, status='cancelling')
            self.event(run_id, 'cancel_requested')
        return self.detail(run_id)

    def close(self):
        if self.cancel_event:
            self.cancel_event.set()
        if self.bridge:
            self.bridge.close()
        if self.thread:
            self.thread.join(timeout=SQL_TIMEOUT_S)
        with self.condition:
            deadline = time.monotonic() + SQL_TIMEOUT_S
            while any(self.pending_tools.values()) and time.monotonic() < deadline:
                self.condition.wait(timeout=min(TOOL_POLL_S, deadline-time.monotonic()))
            if self.store and not (self.thread and self.thread.is_alive()) and not any(self.pending_tools.values()):
                self.store.close()
