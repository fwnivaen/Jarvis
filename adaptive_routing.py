"""Local routing and bounded context; no model, network, credentials or new dependencies.

RouteLLM/FrugalGPT inform calibration and cascades, Semantic Router informs local
intent decisions. This implementation keeps the existing Codex execution owner.
"""
import copy
import json
import re
import threading
import time
from dataclasses import asdict, dataclass

POLICY_VERSION = "adaptive-v1"
DEFAULT_MODEL_CALLS = 8
DEFAULT_TOKEN_BUDGET = 120_000
MAX_MODEL_CALLS = 16
MAX_TOKEN_BUDGET = 240_000
UNKNOWN_CALL_RESERVE = 12_000
CONTEXT_CHARS = 24_000
NOTE_CONTEXT_CHARS = 12_000
NOTE_PASSAGE_CHARS = 2_400
MAX_CONTEXT_NOTES = 6
HISTORY_TURNS = 2
HISTORY_CHARS = 1_600
PREFERENCE_CHARS = 2_000
REPORT_CHARS = 2_400
MAX_LOCAL_NOTE_CHARS = 6_000
MAX_CALCULATION_CHARS = 120
MAX_TEAM_WORKERS = 3
MAX_RECORDED_TOKENS = 10 ** 12
CANCELLATION_POLL_S = 0.05
QUICK_EFFORT = "high"
STRONG_EFFORT = "medium"
DEEP_EFFORT = "high"
TOKEN_KEYS = ("inputTokens", "outputTokens", "totalTokens")
MODEL_NAMES = frozenset({"gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra"})
EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max", "ultra"})
NO_WORKERS = re.compile(r"\b(?:do not|don't|never|without|no)\s+(?:(?:use|run|spawn|assign)\s+)?(?:parallel\s+)?(?:workers|agents)\b", re.I)
EXPLICIT_TEAM = re.compile(r"\b(?:use|run|spawn|assign)\b[^.!?]{0,60}\b(?:workers|agents)\b", re.I)
INDEPENDENT = re.compile(r"\b(?:independently|separately|in parallel)\b", re.I)
CODE = re.compile(r"\b(?:code|debug|exception|traceback|function|patch|regression|deadlock|race condition)\b", re.I)
DEEP = re.compile(r"\b(?:security audit|threat model|prove|proof|deadlock|race condition|contradict\w*|conflicting|ambiguous)\b", re.I)
STRONG = re.compile(r"\b(?:design|architect\w*|diagnos\w*|investigat\w*|tradeoffs?|trade-offs?|multi-step|comprehensive|reconcile)\b", re.I)
FOCUSED = re.compile(r"^\s*(?:summari[sz]e|extract|classify|translate|reformat|rewrite|list|find)\b", re.I)
CALCULATION = re.compile(r"\s*(?:(?:calculate|compute|what is|what's)\s+)?([\d\s.+*/()\-]+)\s*[?=]?\s*", re.I)
SHOW_NOTE = re.compile(r"\s*(?:show|read)\s+note\s+#?(\d+)\s*[.!]?\s*", re.I)
STOP = frozenset("a an and are as at be by for from how i in is it me my of on or that the this to was what with you your".split())


@dataclass(frozen=True)
class Route:
    mode: str = "quick"
    job: str = "general"
    effort: str = QUICK_EFFORT
    workers: int = 0
    reason: str = "focused_default"

    def public(self):
        return dict(asdict(self), policy=POLICY_VERSION)


def decide(question, *, workflow=None, parallel=True, max_workers=MAX_TEAM_WORKERS):
    """Only trusted user text controls scheduling; sources/history never enter here.

    Uncertain requests get one Luna answer/classification, not another router LLM.
    Semantic similarity alone is not evidence that a task is easy.
    """
    job = "code" if CODE.search(question) else "document" if workflow == "document" else "general"
    deep = bool(DEEP.search(question))
    independent = bool(INDEPENDENT.search(question) and
                       (len(re.findall(r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s+", question)) > 1
                        or question.count(";") > 0))
    # The live pilot found a four-call team substantially slower and larger than
    # one strong answer. Require a user-selected workflow or explicit workers
    # until broader calibration demonstrates a useful automatic split.
    team = bool(workflow or EXPLICIT_TEAM.search(question))
    if team and parallel and not NO_WORKERS.search(question):
        return Route("team", job, DEEP_EFFORT if deep else STRONG_EFFORT,
                     min(MAX_TEAM_WORKERS, max_workers), "explicit_workflow" if workflow else "independent_work")
    if deep or CODE.search(question) and not FOCUSED.search(question) or STRONG.search(question) or team or independent:
        return Route("strong", job, DEEP_EFFORT if deep else STRONG_EFFORT, reason="complex_reasoning")
    return Route(job=job)


def local_answer(question, notes, calculate):
    """Only exact, bounded, side-effect-free commands can bypass inference."""
    match = CALCULATION.fullmatch(question)
    if match and len(match[1]) <= MAX_CALCULATION_CHARS:
        try:
            value = calculate(match[1].strip())
            return {"answer": str(value), "about_notes": False, "nodes": []}
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
            return None
    match = SHOW_NOTE.fullmatch(question)
    if match:
        note = next((n for n in notes if n.get("id") == int(match[1])), None)
        if note and len(note.get("text", "")) <= MAX_LOCAL_NOTE_CHARS:
            return {"answer": note["text"], "about_notes": True, "nodes": [note["id"]]}
    return None


def words(value):
    return set(re.findall(r"\w+", value.casefold())) - STOP


def compact_notes(notes, query):
    terms = words(query)
    ranked = sorted(enumerate(notes), key=lambda item: (
        -len(terms & words(item[1].get("title", ""))) * MAX_CONTEXT_NOTES
        -len(terms & words(item[1].get("text", ""))), item[0]))
    selected, remaining = [], NOTE_CONTEXT_CHARS
    for _, note in ranked[:MAX_CONTEXT_NOTES]:
        text = note.get("text", "")
        chunks = [text[i:i + NOTE_PASSAGE_CHARS] for i in range(0, len(text), NOTE_PASSAGE_CHARS)] or [""]
        chunk = max(enumerate(chunks), key=lambda item: (len(terms & words(item[1])), -item[0]))[1]
        chunk = chunk[:remaining]
        row = {key: note[key] for key in ("id", "title", "stable_id", "revision") if key in note}
        row.update(text=chunk, excerpt=len(chunk) < len(text))
        selected.append(row)
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return selected


def compact_payload(payload):
    """No answer cache: mutable sources are fetched and validated every run."""
    value = copy.deepcopy(payload)
    query = str(value.get("question", "")) + " " + str(value.get("assignment", ""))
    notes = value.get("notes", [])
    value["notes"] = compact_notes(notes, query)
    history = value.get("history", [])
    value["history"] = [{key: str(turn[key])[:HISTORY_CHARS] for key in ("question", "answer") if key in turn}
                        for turn in history[-HISTORY_TURNS:]]
    preferences = copy.deepcopy(value.get("preferences"))
    if "preferences" in value:
        remaining = PREFERENCE_CHARS
        prefs = {}
        for key, text in value["preferences"].items():
            if remaining <= 0:
                break
            prefs[key] = str(text)[:remaining]
            remaining -= len(key) + len(prefs[key])
        value["preferences"] = prefs
    reports_compacted = False
    for key in ("worker_results", "peer_reports"):
        for row in value.get(key, []):
            if isinstance(row.get("answer"), str):
                reports_compacted |= len(row["answer"]) > REPORT_CHARS
                row["answer"] = row["answer"][:REPORT_CHARS]
    value["context_limits"] = {"excerpted_notes": any(n["excerpt"] for n in value["notes"]),
        "omitted_notes": len(value["notes"]) < len(notes), "history_compacted": value.get("history") != history,
        "preferences_compacted": value.get("preferences") != preferences, "reports_compacted": reports_compacted,
        "instruction": "Excerpts may omit relevant material. Retrieve missing evidence with authorized tools or disclose the gap. Never imply a full-document review from excerpts."}
    if len(json.dumps(value, ensure_ascii=True)) > CONTEXT_CHARS:
        # Fail explicitly rather than silently removing assignments, constraints or evidence.
        raise RoutingBudgetError("context_budget_exhausted")
    return value


class RoutingBudgetError(Exception):
    def __init__(self, code="model_budget_exhausted"):
        self.code = code
        super().__init__(code)


class CancellationSignal:
    """Read-only union: either user Stop or the shared budget interrupts a turn."""
    def __init__(self, *events):
        self.events = events

    def is_set(self):
        return any(event.is_set() for event in self.events)

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.is_set():
            remaining = CANCELLATION_POLL_S if deadline is None else min(CANCELLATION_POLL_S, deadline - time.monotonic())
            if remaining <= 0:
                return self.is_set()
            self.events[0].wait(remaining)
        return True


class ModelBudget:
    """Aggregate attempts and observed tokens, with unknown usage kept unknown.

    Token notifications lag actual generation. This is an application guard,
    not an atomic provider-side token or billing cap. Unknown calls reserve a
    conservative allowance before concurrent admission.
    """
    def __init__(self, max_calls=DEFAULT_MODEL_CALLS, max_tokens=DEFAULT_TOKEN_BUDGET, saved=None):
        if (type(max_calls) is not int or not 1 <= max_calls <= MAX_MODEL_CALLS or
                type(max_tokens) is not int or not 1 <= max_tokens <= MAX_TOKEN_BUDGET):
            raise ValueError("Invalid model budget")
        if saved is not None:
            if not isinstance(saved, list) or len(saved) > max_calls:
                raise ValueError("Invalid saved model budget")
            for row in saved:
                if (not isinstance(row, dict) or set(row) - ({"model", "effort", "role"} | set(TOKEN_KEYS)) or
                        row.get("model") not in MODEL_NAMES or row.get("effort") not in EFFORTS or
                        not isinstance(row.get("role"), str) or not re.fullmatch(r"(?:answer|brain|dispatch|vision|worker|reviewer|worker-[1-3])", row["role"]) or
                        any(row.get(key) is not None and (type(row[key]) is not int or not 0 <= row[key] <= MAX_RECORDED_TOKENS)
                            for key in TOKEN_KEYS)):
                    raise ValueError("Invalid saved model budget")
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.calls = copy.deepcopy(saved or [])
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        if self.reserved_tokens() > self.max_tokens:
            self.cancel.set()

    def reserved_tokens(self):
        return sum(row.get("totalTokens") if row.get("totalTokens") is not None else UNKNOWN_CALL_RESERVE
                   for row in self.calls)

    def reserve(self, model, effort, role):
        with self.lock:
            if (self.cancel.is_set() or len(self.calls) >= self.max_calls or
                    self.reserved_tokens() + UNKNOWN_CALL_RESERVE > self.max_tokens):
                raise RoutingBudgetError()
            if model not in MODEL_NAMES or effort not in EFFORTS:
                raise RoutingBudgetError("invalid_routing_profile")
            self.calls.append(dict(model=model, effort=effort, role=role, totalTokens=None))
            return len(self.calls) - 1

    def observe(self, index, values):
        with self.lock:
            row = self.calls[index]
            for key in TOKEN_KEYS:
                if type(values.get(key)) is int and values[key] >= 0:
                    row[key] = max(row.get(key) or 0, values[key])
            if self.reserved_tokens() > self.max_tokens:
                self.cancel.set()
                raise RoutingBudgetError()

    def snapshot(self):
        with self.lock:
            complete = all(row.get("totalTokens") is not None for row in self.calls)
            return {"policy": POLICY_VERSION, "model_calls": len(self.calls),
                    "total_tokens": (sum(row.get("totalTokens") or 0 for row in self.calls)
                        if complete or any(row.get("totalTokens") is not None for row in self.calls) else None),
                    "usage_complete": complete, "unreported_calls": sum(row.get("totalTokens") is None for row in self.calls),
                    "max_model_calls": self.max_calls, "max_observed_tokens": self.max_tokens,
                    "calls": copy.deepcopy(self.calls)}
