"""Bounded paired routing check with synthetic sources and objective answer checks.

Default is a zero-spend policy preview. --live uses only the existing signed-in
Codex transport. Results are smoke evidence, not statistically proven savings.
No private notes, credentials, model reasoning or protocol messages are recorded.
"""
import argparse
import hashlib
import json
import re
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import adaptive_routing as routing
from codex_bridge import BridgeError, CodexBridge
from ultra import Settings, UltraJarvis

MAX_PILOT_CALLS = 24
MAX_PILOT_SECONDS = 480
CASE_TIMEOUT_S = 90
WORKER_TIMEOUT_S = 45
OUTPUT_MODE = 0o600
SYSTEM = ("Answer only from the supplied synthetic sources. Be concise. Cite source IDs and exact quotes for source facts. "
          "Do not claim actions, access outside the supplied evidence, or private reasoning. "
          "For a requested exact answer, the answer string must contain only that answer.")
NOTES = [
    {"id": 7, "title": "Project budget", "text": "The approved budget is 120 pounds. Revenue is 200 pounds.", "revision": "pilot-1"},
    {"id": 8, "title": "Revised budget", "text": "Revision 2 supersedes the original budget: the approved budget is 150 pounds.", "revision": "pilot-2"},
    {"id": 9, "title": "Dependency rules", "text": "Tasks A and B can start immediately. C needs both A and B. D needs C. A takes 2 hours; B takes 5 hours; C takes 3 hours; D takes 1 hour.", "revision": "pilot-3"},
]
CASES = (
    {"id": "arithmetic", "question": "Calculate (120 + 200) / 4. Answer only with the number.",
     "notes": [], "pattern": r"^80[.!]?$"},
    {"id": "exact-note", "question": "show note 7", "notes": [NOTES[0]], "pattern": r"120.*200", "nodes": [7]},
    {"id": "focused", "question": "What is the approved budget in Project budget? Give a short answer.",
     "notes": [NOTES[0]], "pattern": r"\b120\b", "nodes": [7]},
    {"id": "planning", "question": "Design the fastest schedule for the dependency rules with unlimited workers. Give the total elapsed hours and explain the critical path briefly.",
     "notes": [NOTES[2]], "pattern": r"\b9\b", "nodes": [9]},
    {"id": "conflicting-sources", "question": "Reconcile these conflicting budget sources. Which budget currently applies and why?",
     "notes": NOTES[:2], "pattern": r"\b150\b", "nodes": [8]},
    {"id": "team", "question": "Use two agents: independently extract original budget and revenue from Project budget; separately check the revised budget. Combine the three amounts and say which budget is current.",
     "notes": NOTES[:2], "pattern": r"(?s)(?=.*\b120\b)(?=.*\b200\b)(?=.*\b150\b)", "nodes": [7, 8]},
)


class CountingBridge:
    def __init__(self, bridge):
        self.bridge, self.calls = bridge, []
        self.started = time.monotonic()
        self.lock = threading.Lock()

    def complete(self, **call):
        row = {'model': call['model'], 'effort': call['effort'], 'total_tokens': None}
        with self.lock:
            if len(self.calls) >= MAX_PILOT_CALLS or time.monotonic() - self.started >= MAX_PILOT_SECONDS:
                raise BridgeError('model_budget_exhausted')
            self.calls.append(row)
        observer = call['observer']
        def observe(values):
            row.update({key: value for key, value in values.items() if key in routing.TOKEN_KEYS and type(value) is int and value >= 0})
            row['total_tokens'] = values.get('totalTokens', row['total_tokens'])
            observer(values)
        try:
            return self.bridge.complete(**dict(call, observer=observe))
        except BridgeError as error:
            row['error'] = error.code
            raise

    def close(self):
        self.bridge.close()


def objective_check(case, result):
    return (not result.get('error') and not result.get('partial')
            and re.search(case['pattern'], result['answer'], re.I | re.S) is not None
            and set(case.get('nodes', [])) <= set(result['nodes']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--case', action='append', choices=[case['id'] for case in CASES],
                        help='Run only selected cases, preserving prior evidence in a separate output file.')
    parser.add_argument('--arm', choices=('both', 'astra', 'adaptive'), default='both')
    args = parser.parse_args()
    cases = [case for case in CASES if not args.case or case['id'] in args.case]
    arms = ('astra', 'adaptive') if args.arm == 'both' else (args.arm,)
    if args.output and (args.output.is_symlink() or not args.output.resolve().is_relative_to(ROOT / '.local')):
        parser.error('Evidence output must be a regular file beneath JARVIS .local.')
    if not args.live:
        print(json.dumps({'live_model_calls': 0, 'arms': arms, 'cases': [dict(id=case['id'], route=routing.decide(case['question']).public()) for case in cases]}, indent=2))
        return
    import server
    bridge = CountingBridge(CodexBridge(server.find_codex(), server.DISABLED_FEATURES,
        tuple(value for value in server.CLI_OVERRIDES if not value.startswith('model_reasoning_effort='))))
    config = replace(Settings(), enabled=True, terminal_monitor_enabled=False, checkpoint_enabled=False,
        tools_enabled=False, worker_retries=1, request_timeout_s=CASE_TIMEOUT_S, worker_timeout_s=WORKER_TIMEOUT_S)
    report = {'policy': routing.POLICY_VERSION, 'synthetic_sources': True, 'live_models': True,
        'baseline': 'Astra High in the same checked app-server harness, not legacy CLI latency',
        'cost': 'unknown; token/credit rates do not establish included-allowance savings',
        'selected_cases': [case['id'] for case in cases], 'selected_arms': arms,
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ('adaptive_routing.py', 'ultra.py', 'workflow_runtime.py', 'codex_bridge.py', 'tools/evaluate_routing.py')}, 'results': []}
    try:
        # No identities or credit balances are returned or recorded.
        bridge.bridge.require_included_usage(time.monotonic() + CASE_TIMEOUT_S)
        report['catalog'] = {model: [row['reasoningEffort'] for row in data.get('supportedReasoningEfforts', [])]
            for model, data in bridge.bridge._models.items()}
        for case in cases:
            for arm in arms:
                start = time.monotonic()
                before = len(bridge.calls)
                runtime = UltraJarvis(lambda: bridge)
                candidate = replace(config, adaptive_routing_enabled=arm == 'adaptive')
                result = runtime.answer(candidate, SYSTEM, case['notes'], [], case['question'],
                    manual_model='gpt-6-astra' if arm == 'astra' else None)
                calls = bridge.calls[before:]
                row = {'case': case['id'], 'arm': arm, 'passed': objective_check(case, result),
                    'elapsed_s': round(time.monotonic() - start, 3), 'model_calls': len(calls),
                    'calls': calls, 'route': result['ultra'].get('routing'),
                    'usage_complete': all(call['total_tokens'] is not None for call in calls),
                    'reported_tokens': sum(call['total_tokens'] or 0 for call in calls)
                        if not calls or any(call['total_tokens'] is not None for call in calls) else None,
                    'partial': bool(result.get('partial')), 'error': bool(result.get('error'))}
                report['results'].append(row)
                print(json.dumps({key: row[key] for key in ('case', 'arm', 'passed', 'elapsed_s', 'model_calls', 'reported_tokens')}), flush=True)
                if any(call.get('error') in ('quota_exhausted', 'usage_unavailable', 'subscription_required', 'model_budget_exhausted') for call in calls):
                    report['stopped'] = 'Usage or pilot budget admission refused; no fallback.'
                    return
    except BridgeError as error:
        report['blocked'] = error.code
    finally:
        bridge.close()
        report['complete'] = len(report['results']) == len(cases) * len(arms)
        report['all_passed'] = report['complete'] and all(row['passed'] for row in report['results'])
        report['total_model_calls'] = len(bridge.calls)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            import os
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), OUTPUT_MODE)
            with os.fdopen(descriptor, 'w') as output:
                json.dump(report, output, indent=2)
                output.write('\n')
        print(json.dumps({key: report[key] for key in ('complete', 'all_passed', 'total_model_calls')}), flush=True)


if __name__ == '__main__':
    main()
