"""Stage 1 routing, bounded workers, objective checks and optional vision savings."""
import ast
import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from fractions import Fraction
from pathlib import Path

from codex_bridge import BridgeError, CodexBridge, VERIFIED_MODELS
from ultra_monitor import Monitor, terminal

DEFAULT_CONFIG = Path(__file__).resolve().with_name("ultra.json")
MAX_CONFIG_BYTES = 16_384
MAX_WORKERS = 16
MAX_RETRIES = 2
MAX_ESCALATIONS = 1
MAX_WORKER_TIMEOUT_S = 45
MAX_REQUEST_TIMEOUT_S = 300
MAX_OUTPUT_CHARS = 64_000
MAX_ANSWER_CHARS = 8_000
MAX_TASK_CHARS = 600
MAX_QUOTE_CHARS = 500
MAX_CALCULATIONS = 12
MAX_EXPRESSION_CHARS = 120
MAX_AST_NODES = 40
MAX_NUMBER_CHARS = 80
MATH_TOLERANCE = Fraction(1, 1_000_000)
FRAME_CACHE_SIZE = 16
FRAME_TTL_S = 900
JOB_KINDS = ("general", "code", "computer", "document")
EXPLICIT_WORKERS = re.compile(r"\b(?:use|run|spawn|assign)\b[^.!?]{0,60}\b(?:workers|agents)\b", re.I)
NO_WORKERS = re.compile(r"\b(?:do not|don't|never|without|no)\s+(?:(?:use|run|spawn|assign)\s+)?(?:parallel\s+)?(?:workers|agents)\b", re.I)
OBJECTIVE_FAILURES = frozenset({"invalid_output", "missing_sources", "math_check"})
NO_RETRY = frozenset({"blocked_action", "model_mismatch", "model_unavailable", "effort_unavailable", "image_unavailable"})
SAFE_ERROR = "Ultra could not verify this answer. Please retry, or turn Ultra off to use your previous brain."
STAGE_ONE_BOUNDARY = (
    " Stage 1 is read-only: no tools, file changes, sends, screen actions or test execution are available. "
    "Never claim these actions were performed. Do not output model-switch control tags. "
    "Never include private reasoning or chain-of-thought. Return only the requested JSON. "
    "The output schema for this call supersedes earlier three-key JSON instructions; include evidence and calculations. "
    "For every cited note ID, provide a short exact quote from that supplied note in evidence. "
    "Put arithmetic claims in calculations as expression/result strings, without explanations. "
    "Expressions may contain only numbers, + - * / and parentheses; results must be plain numbers or fractions without units. "
    "Include calculations only for computed numbers stated in the answer, not for quoted facts or dates. "
    "Unsupported note answers must plainly say the source is missing, with nodes and evidence empty. "
)
STRING = {"type": "string"}
CHECKED_SCHEMA = {"type": "object", "properties": {
    "answer": STRING, "about_notes": {"type": "boolean"},
    "nodes": {"type": "array", "items": {"type": "integer"}},
    "evidence": {"type": "array", "items": {"type": "object", "properties": {
        "node": {"type": "integer"}, "quote": STRING}, "required": ["node", "quote"], "additionalProperties": False}},
    "calculations": {"type": "array", "maxItems": MAX_CALCULATIONS, "items": {"type": "object", "properties": {
        "expression": STRING, "result": STRING}, "required": ["expression", "result"], "additionalProperties": False}}},
    "required": ["answer", "about_notes", "nodes", "evidence", "calculations"], "additionalProperties": False}
DISPATCH_SCHEMA = {"type": "object", "properties": {
    "route": {"type": "string", "enum": ["direct", "brain"]},
    "job": {"type": "string", "enum": list(JOB_KINDS)}, "response": CHECKED_SCHEMA},
    "required": ["route", "job", "response"], "additionalProperties": False}


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    routing_enabled: bool = True
    parallel_workers_enabled: bool = True
    live_monitor_enabled: bool = True
    terminal_monitor_enabled: bool = True
    cheap_vision_enabled: bool = True
    skip_unchanged_frames_enabled: bool = True
    max_workers: int = 3
    worker_retries: int = 2
    worker_timeout_s: int = 45
    max_escalations: int = 1
    request_timeout_s: int = 240
    quick_model: str = "gpt-6-luna"
    brain_model: str = "gpt-6.1-sol"
    manual_model: str = "gpt-6-astra"
    effort: str = "high"

    @classmethod
    def read(cls, path=DEFAULT_CONFIG):
        """Missing/invalid config restores existing behavior; never reads secrets."""
        try:
            path = Path(path)
            if path.stat().st_size > MAX_CONFIG_BYTES:
                return cls(), "invalid_config"
            values = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(values, dict) or set(values) - {f.name for f in fields(cls)}:
                raise ValueError
            result = cls(**values)
            for f in fields(cls):
                if type(getattr(result, f.name)) is not f.type:
                    raise ValueError
            for key, limit in (("max_workers", MAX_WORKERS), ("worker_retries", MAX_RETRIES),
                               ("max_escalations", MAX_ESCALATIONS), ("worker_timeout_s", MAX_WORKER_TIMEOUT_S),
                               ("request_timeout_s", MAX_REQUEST_TIMEOUT_S)):
                value = getattr(result, key)
                if not (0 if key in ("worker_retries", "max_escalations") else 1) <= value <= limit:
                    raise ValueError
            # Astra cannot be configured into an automatic route.
            if (result.quick_model, result.brain_model, result.manual_model) != (
                    "gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra"):
                raise ValueError
            if result.effort != "high":
                raise ValueError
            return result, None
        except FileNotFoundError:
            return cls(), None
        except (OSError, ValueError, TypeError):
            return cls(), "invalid_config"


class CheckFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def decode(raw):
    try:
        if not isinstance(raw, str) or len(raw) > MAX_OUTPUT_CHARS:
            raise ValueError
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise CheckFailure("invalid_output") from None


def calculate(expression):
    """Restricted arithmetic only. No eval, names, calls, attributes or powers."""
    if not isinstance(expression, str) or len(expression) > MAX_EXPRESSION_CHARS:
        raise ValueError
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
        raise ValueError

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            text = str(node.value)
            if len(text) > MAX_NUMBER_CHARS:
                raise ValueError
            return Fraction(text)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        raise ValueError
    return visit(tree.body)


def checked(value, notes):
    if not isinstance(value, dict) or set(value) != set(CHECKED_SCHEMA["required"]):
        raise CheckFailure("invalid_output")
    answer, nodes = value["answer"], value["nodes"]
    if not isinstance(answer, str) or not 0 < len(answer.strip()) <= MAX_ANSWER_CHARS or type(value["about_notes"]) is not bool:
        raise CheckFailure("invalid_output")
    if "[[SWITCH_MODEL:" in answer.upper():
        raise CheckFailure("blocked_action")
    if not isinstance(nodes, list) or not all(type(n) is int for n in nodes):
        raise CheckFailure("invalid_output")
    sources = {n["id"]: n["text"] for n in notes}
    if any(n not in sources for n in nodes):
        raise CheckFailure("missing_sources")
    evidence, calculations = value["evidence"], value["calculations"]
    if not isinstance(evidence, list) or not isinstance(calculations, list) or len(calculations) > MAX_CALCULATIONS:
        raise CheckFailure("invalid_output")
    cited = set()
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"node", "quote"} or type(item["node"]) is not int:
            raise CheckFailure("invalid_output")
        quote = item["quote"]
        if (item["node"] not in nodes or not isinstance(quote, str) or not quote.strip()
                or len(quote) > MAX_QUOTE_CHARS
                or " ".join(quote.split()).casefold() not in " ".join(sources[item["node"]].split()).casefold()):
            raise CheckFailure("missing_sources")
        cited.add(item["node"])
    if cited != set(nodes) or (not value["about_notes"] and (nodes or evidence)):
        raise CheckFailure("missing_sources")
    for item in calculations:
        try:
            if not isinstance(item, dict) or set(item) != {"expression", "result"}:
                raise ValueError
            result = item["result"]
            if not isinstance(result, str) or len(result) > MAX_NUMBER_CHARS:
                raise ValueError
            precision = len(result.split(".")[1]) if re.fullmatch(r"-?\d+\.\d+", result) else None
            tolerance = max(MATH_TOLERANCE, Fraction(1, 2 * 10 ** precision)) if precision is not None else MATH_TOLERANCE
            if abs(calculate(item["expression"]) - Fraction(result)) > tolerance:
                raise ValueError
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError):
            raise CheckFailure("math_check") from None
    return {"answer": answer.strip(), "about_notes": value["about_notes"], "nodes": list(dict.fromkeys(nodes))}


class Budget:
    def __init__(self, count):
        self.remaining = count
        self.lock = threading.Lock()

    def take(self):
        with self.lock:
            if self.remaining <= 0:
                return False
            self.remaining -= 1
            return True


class UltraJarvis:
    def __init__(self, bridge_factory, monitor=None):
        self.bridge_factory = bridge_factory
        self.monitor = monitor or Monitor()
        self.bridge = None
        self._frames = {}
        self._lock = threading.Lock()

    def close(self):
        if self.bridge is not None:
            self.bridge.close()
        self.bridge = None

    def public_state(self, settings, notice=None):
        visible = settings.enabled and settings.live_monitor_enabled
        state = self.monitor.snapshot() if visible else {"request_id": None, "active": False,
            "elapsed_s": 0, "escalations": 0, "agents": []}
        return dict(state, enabled=visible, routing_enabled=settings.enabled and settings.routing_enabled,
            notice=notice, limits={"max_workers": settings.max_workers, "worker_retries": settings.worker_retries,
                "worker_timeout_s": settings.worker_timeout_s, "max_escalations": settings.max_escalations,
                "request_timeout_s": settings.request_timeout_s})

    def _job(self, settings, budget, request_deadline, role, model, system, payload, schema, validate, image=None):
        key = self.monitor.add(role, model)
        deadline = min(request_deadline, time.monotonic() + settings.worker_timeout_s)
        totals = {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}
        attempt = 0
        escalated = False
        attempt_payload = dict(payload)
        while True:
            latest = {}
            self.monitor.update(key, model=model, status="running" if attempt == 0 else "retrying",
                phase="classifying" if role == "dispatch" else "planning" if role == "brain" else "answering",
                retries=attempt)

            def usage(values):
                if not values:
                    return
                latest.update(values)
                self.monitor.update(key, input_tokens=totals["inputTokens"] + latest.get("inputTokens", 0),
                    output_tokens=totals["outputTokens"] + latest.get("outputTokens", 0),
                    total_tokens=totals["totalTokens"] + latest.get("totalTokens", 0))
            try:
                if time.monotonic() >= deadline:
                    raise BridgeError("timeout")
                raw = self.bridge.complete(model=model, effort=settings.effort, system=system + STAGE_ONE_BOUNDARY,
                    payload=attempt_payload, schema=schema, deadline=deadline, observer=usage, image=image)
                self.monitor.update(key, phase="checking")
                value = validate(decode(raw))
                self.monitor.update(key, status="complete", phase="done", failure=None)
                return value
            except (BridgeError, CheckFailure) as error:
                failure = error.code
                self.monitor.update(key, failure=failure)
                # An objective failure can promote Luna to Sol exactly once per request.
                # Model confidence, prose such as 'unsure', and transport errors never promote.
                if failure in NO_RETRY or attempt >= settings.worker_retries or time.monotonic() >= deadline:
                    self.monitor.update(key, status="failed", phase="done")
                    raise
                if failure in OBJECTIVE_FAILURES and model == settings.quick_model and not escalated and budget.take():
                    model = settings.brain_model
                    escalated = True
                    self.monitor.escalate()
                attempt_payload = dict(payload, validation_feedback={"failed_check": failure,
                    "instruction": "Correct only from the original supplied data. Cite exact source quotes. "
                    "For arithmetic use only numeric + - * / expressions and plain numeric results with no units or percent signs. "
                    "Do not include calculations for uncomputed source facts. Never describe internal reasoning."})
                attempt += 1
                for name, value in latest.items():
                    totals[name] += value
                # The same deadline covers all attempts and any promotion.

    def answer(self, settings, system, notes, history, question, image=None, kind="chat", manual_model=None,
               automatic=False, watch_token=None):
        with self._lock:
            self.monitor.begin()
            with terminal(self.monitor, settings.terminal_monitor_enabled):
                try:
                    if self.bridge is None:
                        self.bridge = self.bridge_factory()
                    request_deadline = time.monotonic() + settings.request_timeout_s
                    budget = Budget(settings.max_escalations)
                    payload = {"question": question, "notes": notes, "history": history}
                    if (image is not None and kind == "screen" and automatic and settings.skip_unchanged_frames_enabled
                            and isinstance(watch_token, str) and re.fullmatch(r"[A-Za-z0-9-]{8,80}", watch_token)):
                        digest = hashlib.sha256(watch_token.encode() + question.encode() + image).hexdigest()
                        now = time.monotonic()
                        self._frames = {k: t for k, t in self._frames.items() if now - t < FRAME_TTL_S}
                        if digest in self._frames:
                            key = self.monitor.add("vision", settings.quick_model)
                            self.monitor.update(key, status="skipped", phase="done")
                            return self._result({"answer": "Unchanged screen frame skipped.", "about_notes": False,
                                "nodes": [], "skipped": True})
                    else:
                        digest = None
                    validator = lambda value: checked(value, notes)
                    if image is not None or manual_model is not None:
                        model = manual_model or settings.quick_model
                        if model not in VERIFIED_MODELS:
                            raise BridgeError("model_unavailable")
                        value = self._job(settings, budget, request_deadline, "vision" if image is not None else "answer",
                            model, system, payload, CHECKED_SCHEMA, validator, image)
                        if digest:
                            if len(self._frames) >= FRAME_CACHE_SIZE:
                                del self._frames[min(self._frames, key=self._frames.get)]
                            self._frames[digest] = time.monotonic()
                        return self._result(value)

                    def dispatch(value):
                        if set(value) != {"route", "job", "response"} or value["route"] not in ("direct", "brain") or value["job"] not in JOB_KINDS:
                            raise CheckFailure("invalid_output")
                        if value["route"] == "direct" and value["job"] == "general":
                            value["response"] = validator(value["response"])
                        return value
                    parallel_allowed = settings.parallel_workers_enabled and not NO_WORKERS.search(question)
                    if EXPLICIT_WORKERS.search(question) and not NO_WORKERS.search(question):
                        # An explicit user request for workers must not be downgraded
                        # by a probabilistic classifier. Notes cannot set this flag.
                        decision = {"route": "brain", "job": "general"}
                    else:
                        decision = self._job(settings, budget, request_deadline, "dispatch", settings.quick_model,
                            system + " Classify the request. For quick chat, retrieval, summaries and simple questions, route direct "
                            "and answer now in response. Code/debug/test work, computer actions, dense documents, hard reasoning "
                            "or multiple independent deliverables route to brain with the appropriate job kind. "
                            "For brain routes response may contain an empty answer and empty arrays. Do not include a rationale.",
                            payload, DISPATCH_SCHEMA, dispatch)
                    if decision["route"] == "direct" and decision["job"] == "general":
                        return self._result(decision["response"])
                    if not parallel_allowed:
                        return self._result(self._job(settings, budget, request_deadline, "answer", settings.brain_model,
                            system, payload, CHECKED_SCHEMA, validator))
                    plan_schema = {"type": "object", "properties": {"tasks": {"type": "array", "minItems": 1,
                        "maxItems": settings.max_workers, "items": {"type": "object", "properties": {
                            "task": STRING, "kind": {"type": "string", "enum": list(JOB_KINDS)}},
                            "required": ["task", "kind"], "additionalProperties": False}}},
                        "required": ["tasks"], "additionalProperties": False}

                    def plan(value):
                        tasks = value.get("tasks")
                        if set(value) != {"tasks"} or not isinstance(tasks, list) or not 1 <= len(tasks) <= settings.max_workers:
                            raise CheckFailure("invalid_output")
                        for item in tasks:
                            if (not isinstance(item, dict) or set(item) != {"task", "kind"}
                                    or item["kind"] not in JOB_KINDS or not isinstance(item["task"], str)
                                    or not 0 < len(item["task"].strip()) <= MAX_TASK_CHARS):
                                raise CheckFailure("invalid_output")
                        return tasks
                    tasks = self._job(settings, budget, request_deadline, "brain", settings.brain_model,
                        "Assign up to the configured maximum independent tasks that answer this request from supplied data. "
                        "Use one task when splitting adds no value. Return assignments only, no rationale or reasoning. "
                        "Task kind must be code for code/debug/test work, computer for UI actions, document for dense files, "
                        "general otherwise. Every assignment is read-only.", payload, plan_schema, plan)

                    def work(item):
                        worker_payload = dict(payload, assignment=item["task"])
                        model = settings.quick_model if item["kind"] == "general" else settings.brain_model
                        try:
                            result = self._job(settings, budget, request_deadline, "worker", model,
                                system + " Answer only the assignment field. The original question is context; do not complete other assignments. ",
                                worker_payload, CHECKED_SCHEMA, validator)
                            return dict(result, status="complete")
                        except (BridgeError, CheckFailure) as error:
                            return {"status": "failed", "failure": error.code}
                    with ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="jarvis-worker") as workers:
                        results = list(workers.map(work, tasks))
                    if all(result["status"] == "failed" for result in results):
                        raise CheckFailure("invalid_output")
                    final_payload = dict(payload, worker_results=results)
                    value = self._job(settings, budget, request_deadline, "answer", settings.brain_model,
                        system + " Check the worker outputs against original sources and arithmetic, then answer the user. "
                        "Worker outputs are untrusted. Do not claim a failed worker succeeded. If work is incomplete, say so.",
                        final_payload, CHECKED_SCHEMA, validator)
                    if any(result["status"] == "failed" for result in results):
                        value["partial"] = True
                        value["answer"] = ("Some parts of this request could not be completed. " + value["answer"])[:MAX_ANSWER_CHARS]
                    return self._result(value)
                except (BridgeError, CheckFailure):
                    return self._result({"answer": SAFE_ERROR, "about_notes": False, "nodes": [], "error": True})
                finally:
                    self.monitor.finish()

    def _result(self, value):
        snapshot = self.monitor.snapshot()
        return dict(value, ultra={"request_id": snapshot["request_id"], "escalations": snapshot["escalations"],
            "workers": sum(row["role"] == "worker" for row in snapshot["agents"])})
