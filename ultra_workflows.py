"""Small workflow recipes, private checkpoints and deterministic run evaluation.

This module does not execute models or tools. The routing layer supplies validated
reports and budget counters; notes and conversation text are only fingerprinted.
"""
import copy
import hashlib
import json
import math
import os
import re
import secrets
import stat
import threading
import time
from pathlib import Path

DEFAULT_STORE = Path(__file__).resolve().parent / ".local" / "ultra-runs"
SCHEMA_VERSION = 1
RUN_ID_BYTES = 12
MAX_RUN_BYTES = 2 * 1024 * 1024
MAX_RUNS = 100
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = MAX_RUNS
MAX_STRUCTURE_DEPTH = 16
MAX_STRUCTURE_ITEMS = 10000
MAX_STRING_CHARS = 64000
MAX_NUMBER = 10 ** 15
MAX_CHECKS = 256
ELAPSED_DIGITS = 3
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
RUN_ID = re.compile(r"[a-f0-9]{24}\Z")
FINGERPRINT = re.compile(r"[a-f0-9]{64}\Z")
STATE_KEYS = frozenset({"saved_agents", "tool_session", "tool_notes", "phase", "workflow", "context", "plan", "reports", "reviews", "final", "budget",
    "attempts", "elapsed_s", "status", "errors", "checks", "metrics", "decision", "worker_state", "routing_budget"})
FORBIDDEN_KEYS = frozenset({"reasoning", "chain_of_thought", "chainofthought", "raw_response",
    "raw_output", "api_key", "apikey", "authorization", "password", "secret", "system_prompt"})
ENVELOPE_KEYS = frozenset({"version", "run_id", "fingerprint", "created_at", "updated_at", "state"})
RUN_STATUSES = frozenset({"running", "complete", "partial", "failed", "interrupted"})
CONTEXT_KEYS = frozenset({"history", "workflow", "requested_workflow"})
ROLE_COUNT = 3
TEMPLATES = {
    "general": {"id": "general", "label": "General analysis", "roles": [
        {"name": "Analyst", "assignment": "Analyze the main problem and produce concrete findings from supplied evidence."},
        {"name": "Evidence reviewer", "assignment": "Find supporting evidence and identify missing information in the supplied material."},
        {"name": "Cross-checker", "assignment": "Cross-check claims, arithmetic and inconsistencies; report unresolved gaps."}],
        "criteria": ["Answer the original request", "Cite supplied evidence for note claims",
            "Check arithmetic", "Disclose incomplete work"]},
    "research": {"id": "research", "label": "Evidence research", "roles": [
        {"name": "Research analyst", "assignment": "Answer the research question from the supplied sources and identify the strongest supported findings."},
        {"name": "Source reviewer", "assignment": "Compare the supplied sources, track exact supporting excerpts and identify missing sources."},
        {"name": "Fact checker", "assignment": "Check source coverage, conflicting claims and unsupported conclusions."}],
        "criteria": ["Use only available sources", "Tie claims to exact source evidence",
            "Identify source conflicts", "Disclose missing sources"]},
    "code": {"id": "code", "label": "Code review", "roles": [
        {"name": "Technical analyst", "assignment": "Analyze the supplied code and propose the smallest concrete fix; do not claim execution."},
        {"name": "Failure investigator", "assignment": "Inspect supplied errors and code for reproducible causes, edge cases and dependencies."},
        {"name": "Validation reviewer", "assignment": "Review the proposed approach for regressions and specify relevant checks; distinguish suggestions from executed tests."}],
        "criteria": ["Tie findings to supplied code or errors", "Preserve existing behavior",
            "Identify regression risks", "Never claim tests ran without execution evidence"]},
    "document": {"id": "document", "label": "Document analysis", "roles": [
        {"name": "Document analyst", "assignment": "Extract the requested facts and conclusions from the supplied document text."},
        {"name": "Evidence reviewer", "assignment": "Collect exact supporting excerpts and compare relevant sections, tables and figures only when supplied."},
        {"name": "Consistency checker", "assignment": "Cross-check numbers, conflicting passages, missing pages and unsupported visual claims."}],
        "criteria": ["Cite document evidence", "Check computed values", "Identify missing content",
            "Distinguish source facts from interpretations"]},
}


def workflow_template(kind="general", workflow=None):
    """Select an explicit recipe or job kind; never classify user text here."""
    if workflow is not None and workflow not in TEMPLATES:
        raise ValueError("Unknown workflow")
    name = workflow or (kind if kind in TEMPLATES else "general")
    return copy.deepcopy(TEMPLATES[name])


def workflow_templates():
    """Recipes contain instructions only, with no user or run content."""
    return [copy.deepcopy(TEMPLATES[name]) for name in TEMPLATES]


def _json_tree(value, depth=0, count=None):
    if count is None:
        count = [0]
    count[0] += 1
    if depth > MAX_STRUCTURE_DEPTH or count[0] > MAX_STRUCTURE_ITEMS:
        raise ValueError("Checkpoint structure too large")
    if value is None or type(value) is bool:
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING_CHARS:
            raise ValueError("Checkpoint string too large")
        return
    if type(value) in (int, float):
        if not math.isfinite(value) or abs(value) > MAX_NUMBER:
            raise ValueError("Invalid checkpoint number")
        return
    if isinstance(value, list):
        for item in value:
            _json_tree(item, depth + 1, count)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > MAX_STRING_CHARS or key.casefold() in FORBIDDEN_KEYS:
                raise ValueError("Invalid checkpoint field")
            _json_tree(item, depth + 1, count)
        return
    raise ValueError("Checkpoint must contain JSON values")


def context_fingerprint(context):
    """Hash all caller-supplied relevant context; never write that context."""
    _json_tree(context)
    raw = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_RUN_BYTES:
        raise ValueError("Context too large")
    return hashlib.sha256(raw).hexdigest()


def _state_valid(state):
    if not isinstance(state, dict) or set(state) - STATE_KEYS:
        raise ValueError("Unknown checkpoint state field")
    _json_tree(state)
    if state.get("status", "running") not in RUN_STATUSES:
        raise ValueError("Invalid checkpoint status")
    if "workflow" in state and state["workflow"] not in TEMPLATES:
        raise ValueError("Invalid checkpoint workflow")
    if "phase" in state and state["phase"] not in {"planned", "workers", "drafting", "drafts_ready", "reviewing", "reviewed", "reported", "interrupted"}:
        raise ValueError("Invalid checkpoint phase")
    if "context" in state and (not isinstance(state["context"], dict) or set(state["context"]) - CONTEXT_KEYS):
        raise ValueError("Only original conversation history and requested workflow may be retained")


def _number(value, default=0):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= MAX_NUMBER else default


def evaluation_summary(snapshot, result=None, checks=None):
    """Summarize observed outcomes and counters, without an LLM judge or text."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    result = result if isinstance(result, dict) else {}
    rows = snapshot.get("agents", [])
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    checks = checks if isinstance(checks, list) else []
    passed = sum(item.get("status") == "passed" for item in checks[:MAX_CHECKS] if isinstance(item, dict))
    failed = sum(item.get("status") == "failed" for item in checks[:MAX_CHECKS] if isinstance(item, dict))
    failed_jobs = sum(row.get("status") == "failed" for row in rows)
    complete_jobs = sum(row.get("status") == "complete" for row in rows)
    partial = bool(result.get("partial"))
    error = bool(result.get("error"))
    status = "failed" if error else "partial" if partial else "complete"
    tokens = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        known = [_number(row[field], None) for row in rows if field in row and row[field] is not None]
        known = [value for value in known if value is not None]
        tokens[field] = sum(known) if known else None
    return {"status": status, "partial": partial, "jobs": len(rows),
        "workers": len({row.get("slot") or row.get("id") or index for index, row in enumerate(rows)
            if row.get("role") == "worker"}),
        "completed_jobs": complete_jobs, "failed_jobs": failed_jobs,
        "retries": sum(int(_number(row.get("retries"))) for row in rows),
        "escalations": int(_number(snapshot.get("escalations"))),
        "elapsed_s": round(_number(snapshot.get("elapsed_s")), ELAPSED_DIGITS),
        "checks_passed": passed, "checks_failed": failed,
        "token_usage_complete": bool(rows) and all(_number(row.get("total_tokens"), None) is not None for row in rows),
        **tokens}


class WorkflowStore:
    """Bounded, atomic local checkpoints. Invalid/unavailable data fails closed."""
    def __init__(self, root=DEFAULT_STORE, clock=time.time):
        self.root = Path(root)
        self.clock = clock
        self._lock = threading.RLock()

    def _directory(self):
        if self.root.is_symlink():
            raise OSError("Checkpoint directory cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
        descriptor = os.open(str(self.root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("Checkpoint path is not a directory")
            os.fchmod(descriptor, PRIVATE_DIRECTORY_MODE)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    @staticmethod
    def _ids(run_id, fingerprint=None):
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid run ID")
        if fingerprint is not None and (not isinstance(fingerprint, str) or not FINGERPRINT.fullmatch(fingerprint)):
            raise ValueError("Invalid context fingerprint")

    def _read(self, directory, run_id):
        self._ids(run_id)
        descriptor = os.open(run_id + ".json", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > MAX_RUN_BYTES:
                raise ValueError("Invalid checkpoint file")
            os.fchmod(source.fileno(), PRIVATE_FILE_MODE)
            raw = source.read(MAX_RUN_BYTES + 1)
        if len(raw) > MAX_RUN_BYTES:
            raise ValueError("Checkpoint file too large")
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != ENVELOPE_KEYS:
            raise ValueError("Invalid checkpoint envelope")
        self._ids(value["run_id"], value["fingerprint"])
        if value["version"] != SCHEMA_VERSION or value["run_id"] != run_id:
            raise ValueError("Incompatible checkpoint")
        if any(type(value[key]) not in (int, float) or not math.isfinite(value[key]) for key in ("created_at", "updated_at")):
            raise ValueError("Invalid checkpoint timestamp")
        _state_valid(value["state"])
        return value

    def start(self, fingerprint, state):
        """Return a fresh ID, or None if persistence is unavailable or full."""
        with self._lock:
            try:
                run_id = secrets.token_hex(RUN_ID_BYTES)
                self._ids(run_id, fingerprint)
                _state_valid(state)
                directory = self._directory()
                try:
                    if sum(RUN_ID.fullmatch(name[:-5]) is not None for name in os.listdir(directory) if name.endswith(".json")) >= MAX_RUNS:
                        return None
                finally:
                    os.close(directory)
                return run_id if self.save(run_id, fingerprint, state) else None
            except (OSError, ValueError, TypeError, RecursionError, OverflowError):
                return None

    def save(self, run_id, fingerprint, state):
        with self._lock:
            directory, temporary = None, None
            try:
                self._ids(run_id, fingerprint)
                _state_valid(state)
                directory = self._directory()
                now = self.clock()
                try:
                    previous = self._read(directory, run_id)
                except FileNotFoundError:
                    previous = None
                if previous and previous["fingerprint"] != fingerprint:
                    return False
                value = {"version": SCHEMA_VERSION, "run_id": run_id, "fingerprint": fingerprint,
                    "created_at": previous["created_at"] if previous else now, "updated_at": now, "state": state}
                raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                if len(raw) > MAX_RUN_BYTES:
                    return False
                temporary = "." + run_id + "." + secrets.token_hex(RUN_ID_BYTES) + ".tmp"
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), PRIVATE_FILE_MODE, dir_fd=directory)
                with os.fdopen(descriptor, "wb") as target:
                    os.fchmod(target.fileno(), PRIVATE_FILE_MODE)
                    target.write(raw)
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temporary, run_id + ".json", src_dir_fd=directory, dst_dir_fd=directory)
                temporary = None
                os.fsync(directory)
                return True
            except (OSError, ValueError, TypeError, RecursionError, OverflowError):
                return False
            finally:
                if directory is not None:
                    if temporary is not None:
                        try:
                            os.unlink(temporary, dir_fd=directory)
                        except OSError:
                            pass
                    os.close(directory)

    def load(self, run_id, fingerprint=None):
        directory = None
        try:
            self._ids(run_id, fingerprint)
            with self._lock:
                directory = self._directory()
                value = self._read(directory, run_id)
                if fingerprint is not None and value["fingerprint"] != fingerprint:
                    return None
                return value["state"]
        except (OSError, ValueError, TypeError, RecursionError, OverflowError):
            return None
        finally:
            if directory is not None:
                os.close(directory)

    def list_runs(self, limit=DEFAULT_LIST_LIMIT):
        """Public metadata only: no prompts, reports, context hashes or errors."""
        directory = None
        try:
            if type(limit) is not int or not 1 <= limit <= MAX_LIST_LIMIT:
                raise ValueError("Invalid list limit")
            with self._lock:
                directory = self._directory()
                runs = []
                for name in os.listdir(directory):
                    if not name.endswith(".json") or not RUN_ID.fullmatch(name[:-5]):
                        continue
                    try:
                        value = self._read(directory, name[:-5])
                        state = value["state"]
                        metrics = state.get("metrics")
                        # Recompute from metadata rather than returning an arbitrary stored dict.
                        summary = {key: metrics[key] for key in ("status", "partial", "jobs", "workers", "completed_jobs", "failed_jobs",
                            "retries", "escalations", "elapsed_s", "checks_passed", "checks_failed", "token_usage_complete",
                            "input_tokens", "output_tokens", "total_tokens") if key in metrics} if isinstance(metrics, dict) else None
                        if summary is not None and any(not (item is None or type(item) in (bool, int, float) or
                                key == "status" and item in RUN_STATUSES) for key, item in summary.items()):
                            summary = None
                        runs.append({"run_id": value["run_id"], "workflow": state.get("workflow", "general"),
                            "status": state.get("status", "running"), "phase": state.get("phase", "unknown"),
                            "created_at": value["created_at"], "updated_at": value["updated_at"], "evaluation": summary})
                    except (OSError, ValueError, TypeError, RecursionError, OverflowError):
                        continue
                return sorted(runs, key=lambda row: row["updated_at"], reverse=True)[:limit]
        except (OSError, ValueError, TypeError):
            return []
        finally:
            if directory is not None:
                os.close(directory)
