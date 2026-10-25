"""Routing contracts: model boundary scripted, no credentials or model spending."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import adaptive_routing as routing
import ultra
from codex_bridge import BridgeError
from test_ultra import FakeBridge, NOTES, response, dispatch, QUICK, BRAIN, ASTRA


def settings(**values):
    return replace(ultra.Settings(), enabled=True, adaptive_routing_enabled=True,
                   terminal_monitor_enabled=False, checkpoint_enabled=False, **values)


class PolicyTests(unittest.TestCase):
    def test_unfamiliar_easy_requests_do_not_need_a_separate_router_call(self):
        for question in ('Summarize the note', 'Extract function names from this code', 'Hello', 'What does this mean?'):
            self.assertEqual(routing.decide(question).mode, 'quick', question)

    def test_hard_requests_use_one_strong_model_without_a_team(self):
        for question, effort in (('Design a migration strategy', 'medium'),
                ('Debug this exception', 'medium'), ('Investigate this race condition', 'high'),
                ('Reconcile conflicting sources', 'high')):
            route = routing.decide(question)
            self.assertEqual((route.mode, route.workers, route.effort), ('strong', 0, effort))

    def test_workers_require_a_useful_split_and_respect_explicit_refusal(self):
        self.assertEqual(routing.decide('Use three agents to analyze the notes').mode, 'team')
        independent = routing.decide('Independently analyze A; separately analyze B')
        self.assertEqual((independent.mode, independent.workers), ('strong', 0))
        self.assertNotEqual(routing.decide('Say independently in a sentence').mode, 'team')
        self.assertEqual(routing.decide('Use agents. Do not use workers.').workers, 0)
        self.assertEqual(routing.decide('Use agents', max_workers=16).workers, 3)

    def test_only_exact_safe_commands_bypass_the_model(self):
        self.assertEqual(routing.local_answer('calculate (120 + 200) / 4', NOTES, ultra.calculate)['answer'], '80')
        self.assertEqual(routing.local_answer('show note 7', NOTES, ultra.calculate)['nodes'], [7])
        for question in ('calculate __import__("os")', 'show note 7 and delete it',
                         '2 ** 100', 'calculate 1/0', 'show note 99'):
            self.assertIsNone(routing.local_answer(question, NOTES, ultra.calculate))

    def test_context_selection_preserves_quotes_and_marks_omissions(self):
        text = 'Unrelated material. ' * 300 + 'The project code is ZEBRA.'
        notes = [dict(NOTES[0], text=text), {'id': 8, 'title': 'Other', 'text': 'Nothing.'}]
        payload = {'question': 'What is the project code?', 'notes': notes,
                   'history': [{'question': 'Old', 'answer': 'x' * 3000}] * 5}
        compact = routing.compact_payload(payload)
        self.assertIn('The project code is ZEBRA.', compact['notes'][0]['text'])
        self.assertIn(compact['notes'][0]['text'], text)
        self.assertTrue(compact['context_limits']['excerpted_notes'])
        self.assertTrue(compact['context_limits']['history_compacted'])
        self.assertLess(len(json.dumps(compact)), routing.CONTEXT_CHARS)
        self.assertEqual(len(payload['history']), 5)  # Caller/source data remain intact.

    def test_context_is_not_cached_across_source_revisions(self):
        first = routing.compact_payload({'question': 'Budget?', 'notes': NOTES})
        changed = [dict(NOTES[0], text='The budget is now 150 pounds.', revision='new')]
        second = routing.compact_payload({'question': 'Budget?', 'notes': changed})
        self.assertNotEqual(first['notes'], second['notes'])
        self.assertEqual(second['notes'][0]['revision'], 'new')

    def test_oversized_constraints_fail_instead_of_silently_disappearing(self):
        with self.assertRaises(routing.RoutingBudgetError):
            routing.compact_payload({'question': 'x' * routing.CONTEXT_CHARS, 'notes': NOTES})

    def test_shortened_preferences_and_reports_are_explicit(self):
        result = routing.compact_payload({'question': 'Budget?', 'notes': NOTES,
            'preferences': {'style': 'x' * (routing.PREFERENCE_CHARS + 1)},
            'worker_results': [{'answer': 'x' * (routing.REPORT_CHARS + 1)}]})
        self.assertTrue(result['context_limits']['preferences_compacted'])
        self.assertTrue(result['context_limits']['reports_compacted'])

    def test_invalid_configuration_fails_closed(self):
        for change in ({'adaptive_routing_enabled': 'yes'}, {'model_call_limit': 0},
                       {'observed_token_limit': -1}, {'adaptive_routing_enabled': True, 'max_workers': 4}):
            with tempfile.TemporaryDirectory() as root:
                path = Path(root) / 'flags.json'
                path.write_text(json.dumps(change))
                value, notice = ultra.Settings.read(path)
                self.assertEqual(notice, 'invalid_config')
                self.assertFalse(value.enabled)


class BudgetTests(unittest.TestCase):
    def test_user_stop_and_shared_budget_both_interrupt_waiters(self):
        for index in (0, 1):
            events = [threading.Event(), threading.Event()]
            signal = routing.CancellationSignal(*events)
            self.assertFalse(signal.wait(0))
            events[index].set()
            self.assertTrue(signal.is_set())
            self.assertTrue(signal.wait(0))

    def test_parallel_attempts_share_one_budget(self):
        budget = routing.ModelBudget(max_calls=3)
        def attempt(_):
            try:
                budget.reserve(QUICK, 'high', 'worker')
                return True
            except routing.RoutingBudgetError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(20))), 3)

    def test_cumulative_notifications_are_not_double_counted(self):
        budget = routing.ModelBudget()
        call = budget.reserve(QUICK, 'high', 'answer')
        budget.observe(call, {'totalTokens': 10})
        budget.observe(call, {'totalTokens': 20})
        budget.observe(call, {'totalTokens': 12})
        self.assertEqual(budget.snapshot()['total_tokens'], 20)

    def test_unknown_usage_stays_unknown_and_consumes_reservation(self):
        budget = routing.ModelBudget(max_tokens=routing.UNKNOWN_CALL_RESERVE)
        budget.reserve(QUICK, 'high', 'answer')
        self.assertIsNone(budget.snapshot()['total_tokens'])
        self.assertFalse(budget.snapshot()['usage_complete'])
        with self.assertRaises(routing.RoutingBudgetError):
            budget.reserve(QUICK, 'high', 'answer')

    def test_token_limit_fences_other_calls_and_survives_resume(self):
        budget = routing.ModelBudget(max_tokens=routing.UNKNOWN_CALL_RESERVE)
        call = budget.reserve(QUICK, 'high', 'answer')
        with self.assertRaises(routing.RoutingBudgetError):
            budget.observe(call, {'totalTokens': routing.UNKNOWN_CALL_RESERVE + 1})
        self.assertTrue(budget.cancel.is_set())
        restored = routing.ModelBudget(max_tokens=routing.UNKNOWN_CALL_RESERVE, saved=budget.snapshot()['calls'])
        with self.assertRaises(routing.RoutingBudgetError):
            restored.reserve(BRAIN, 'medium', 'answer')

    def test_corrupt_saved_budgets_cannot_expand_access(self):
        for rows in ([{'model': 'paid/model'}], [{'model': QUICK, 'effort': 'high', 'role': 'worker', 'totalTokens': -1}],
                     [{'model': QUICK, 'effort': 'high', 'role': 'worker', 'secret': 'x'}]):
            with self.assertRaises(ValueError):
                routing.ModelBudget(saved=rows)


class ExecutionTests(unittest.TestCase):
    def run_request(self, question, handler, **options):
        fake = FakeBridge(handler)
        runtime = ultra.UltraJarvis(lambda: fake)
        result = runtime.answer(settings(), 'Use sources.', NOTES, [], question, **options)
        return result, fake, runtime

    def test_local_arithmetic_spends_no_model_calls(self):
        result, fake, _ = self.run_request('calculate 14*9', lambda _: self.fail('No inference allowed'))
        self.assertEqual(result['answer'], '126')
        self.assertEqual(fake.calls, [])
        self.assertEqual(result['ultra']['model_usage']['model_calls'], 0)

    def test_small_request_uses_one_luna_call(self):
        result, fake, _ = self.run_request('Summarize the note', lambda _: dispatch())
        self.assertEqual([(c['model'], c['effort']) for c in fake.calls], [(QUICK, 'high')])
        self.assertEqual(result['ultra']['workers'], 0)
        self.assertIn(ultra.STAGE_ONE_BOUNDARY, fake.calls[0]['system'])
        self.assertNotIn('tools', fake.calls[0])

    def test_focused_code_can_stay_on_luna(self):
        result, fake, _ = self.run_request('Extract function names from code', lambda _: dispatch(job='code'))
        self.assertFalse(result.get('error'))
        self.assertEqual([c['model'] for c in fake.calls], [QUICK])

    def test_complex_request_uses_sol_once_without_dispatch_or_review(self):
        _, fake, _ = self.run_request('Design a migration strategy', lambda _: response())
        self.assertEqual([(c['model'], c['effort']) for c in fake.calls], [(BRAIN, 'medium')])

    def test_luna_can_request_sol_without_spawning_a_crew(self):
        result, fake, _ = self.run_request('An unfamiliar question',
            lambda c: dispatch('brain') if c['schema'] is ultra.DISPATCH_SCHEMA else response())
        self.assertEqual([c['model'] for c in fake.calls], [QUICK, BRAIN])
        self.assertEqual(result['ultra']['workers'], 0)

    def test_team_uses_one_plan_small_workers_one_synthesis_and_no_peer_rounds(self):
        def model(call):
            if 'tasks' in call['schema']['properties']:
                return {'tasks': [{'task': 'Read budget', 'kind': 'general'}, {'task': 'Read revenue', 'kind': 'general'}]}
            value = response(note=True)
            if 'unresolved_issues' in call['schema']['properties']:
                value['unresolved_issues'] = []
            self.assertNotIn('peer_reports', call['payload'])
            return value
        result, fake, _ = self.run_request('Use two agents to analyze the notes', model)
        self.assertFalse(result.get('error'), result)
        self.assertEqual(len(fake.calls), 4)
        self.assertEqual([(c['model'], c['effort']) for c in fake.calls if 'assignment' in c['payload']],
                         [(QUICK, 'high'), (QUICK, 'high')])
        self.assertTrue(all(c['effort'] == 'medium' for c in fake.calls if c['model'] == BRAIN))

    def test_objective_failure_promotes_once_and_counts_failed_attempt(self):
        def model(call):
            value = dispatch()
            if call['model'] == QUICK:
                value['response'] = response(note=True)
                value['response']['evidence'][0]['quote'] = 'Invented quote.'
            return value
        result, fake, _ = self.run_request('Summarize the note', model)
        self.assertEqual([c['model'] for c in fake.calls], [QUICK, BRAIN])
        self.assertEqual(result['ultra']['model_usage']['model_calls'], 2)
        self.assertEqual(result['ultra']['escalations'], 1)

    def test_quota_and_auth_failures_are_terminal(self):
        for code in ('quota_exhausted', 'usage_unavailable', 'subscription_required'):
            def fail(_):
                raise BridgeError(code)
            result, fake, _ = self.run_request('Summarize the note', fail)
            self.assertTrue(result['error'])
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(result['ultra']['escalations'], 0)

    def test_manual_astra_remains_an_explicit_override(self):
        _, fake, _ = self.run_request('Summarize the note', lambda _: response(), manual_model=ASTRA)
        self.assertEqual([c['model'] for c in fake.calls], [ASTRA])

    def test_budget_refusal_does_not_retry_or_escalate(self):
        fake = FakeBridge(lambda _: dispatch('brain'))
        runtime = ultra.UltraJarvis(lambda: fake)
        result = runtime.answer(settings(model_call_limit=1), 'Sources.', NOTES, [], 'Unknown question')
        self.assertTrue(result['error'])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(result['ultra']['model_usage']['model_calls'], 1)

    def test_team_checkpoint_keeps_aggregate_budget_on_cached_resume(self):
        from ultra_workflows import WorkflowStore
        def model(call):
            if 'tasks' in call['schema']['properties']:
                return {'tasks': [{'task': 'Read budget', 'kind': 'general'}]}
            value = response(note=True)
            if 'unresolved_issues' in call['schema']['properties']:
                value['unresolved_issues'] = []
            return value
        with tempfile.TemporaryDirectory() as root:
            fake = FakeBridge(model)
            runtime = ultra.UltraJarvis(lambda: fake, workflow_store=WorkflowStore(Path(root)))
            config = replace(settings(), checkpoint_enabled=True)
            question = 'Use workers to read budget'
            result = runtime.answer(config, 'Sources.', NOTES, [], question)
            self.assertIsNotNone(result['ultra']['run_id'])
            before = len(fake.calls)
            resumed = runtime.answer(config, 'Sources.', NOTES, [], question, resume_run=result['ultra']['run_id'])
            self.assertFalse(resumed.get('error'), resumed)
            self.assertEqual(len(fake.calls), before)
            self.assertEqual(resumed['ultra']['model_usage'], result['ultra']['model_usage'])


try:
    import langgraph.checkpoint.sqlite
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False


@unittest.skipUnless(GRAPH_AVAILABLE, 'Optional LangGraph environment required')
class GraphTests(unittest.TestCase):
    def test_complex_focused_work_uses_one_sol_call(self):
        from test_workflow_runtime import Model, NOTE
        from ultra_tools import Registry
        from workflow_runtime import WorkflowService
        config = settings()
        model = Model()
        registry = Registry(lambda: config, {'notes_search': lambda query: {'notes': [NOTE]}, 'note_read': lambda id: NOTE})
        with tempfile.TemporaryDirectory() as root:
            service = WorkflowService(lambda: config, registry, lambda: model, threading.BoundedSemaphore(1),
                                      'Use sources.', root=Path(root))
            try:
                run = service.start('Design a budget strategy', 'general')
                service.thread.join(8)
                self.assertEqual(service.detail(run['id'])['status'], 'complete')
                self.assertEqual([(c['model'], c['effort']) for c in model.calls], [(BRAIN, 'medium')])
            finally:
                service.close()

    def test_shared_budget_interrupts_other_active_workflow_turns(self):
        from test_workflow_runtime import Model, NOTE
        from ultra_tools import Registry
        from workflow_runtime import WorkflowService
        config = settings(observed_token_limit=40_000)
        class ConcurrentModel(Model):
            def __init__(self):
                super().__init__()
                self.barrier = threading.Barrier(3)
                self.interrupted = 0

            def complete(self, **call):
                with self.lock:
                    self.calls.append(call)
                    index = len(self.calls)
                self.barrier.wait(5)
                if index == 1:
                    call['observer']({'totalTokens': 50_000})
                    raise AssertionError('Over-budget observer must terminate this turn')
                if call['cancel_event'].wait(5):
                    with self.lock:
                        self.interrupted += 1
                    raise BridgeError('cancelled')
                raise AssertionError('Other active turns did not receive shared cancellation')
        model = ConcurrentModel()
        registry = Registry(lambda: config, {'notes_search': lambda query: {'notes': [NOTE]}, 'note_read': lambda id: NOTE})
        with tempfile.TemporaryDirectory() as root:
            service = WorkflowService(lambda: config, registry, lambda: model, threading.BoundedSemaphore(1),
                                      'Use sources.', root=Path(root))
            try:
                run = service.start('Research budget evidence', 'research')
                service.thread.join(8)
                result = service.detail(run['id'])
                self.assertEqual((result['status'], result['error']), ('failed', 'model_budget_exhausted'), result)
                self.assertEqual(len(model.calls), 3)
                self.assertEqual(model.interrupted, 2)
                self.assertEqual(result['model_usage']['model_calls'], 3)
                self.assertFalse(result['can_retry'])
                self.assertEqual(result['cleanup'], 'complete')
            finally:
                service.close()

    def test_workflow_skips_restatement_review_and_persists_call_budget(self):
        from test_workflow_runtime import Model, NOTE
        from ultra_tools import Registry
        from workflow_runtime import WorkflowService
        config = settings()
        model = Model()
        registry = Registry(lambda: config, {'notes_search': lambda query: {'notes': [NOTE]}, 'note_read': lambda id: NOTE})
        with tempfile.TemporaryDirectory() as root:
            service = WorkflowService(lambda: config, registry, lambda: model, threading.BoundedSemaphore(1),
                                      'Use sources.', root=Path(root))
            try:
                run = service.start('Summarize budget', 'general')
                service.thread.join(8)
                result = service.detail(run['id'])
                self.assertEqual(result['status'], 'complete', result)
                self.assertEqual(len(model.calls), 1)
                self.assertEqual(result['model_usage']['model_calls'], 1)
                self.assertTrue(result['model_usage']['usage_complete'])
            finally:
                service.close()

    def test_workflow_quota_is_terminal_and_budget_is_not_reset_by_resume(self):
        from test_workflow_runtime import Model, NOTE
        from ultra_tools import Registry
        from workflow_runtime import WorkflowService
        config = settings(model_call_limit=1)
        model = Model()
        model.failure = 'quota_exhausted'
        registry = Registry(lambda: config, {'notes_search': lambda query: {'notes': [NOTE]}, 'note_read': lambda id: NOTE})
        with tempfile.TemporaryDirectory() as root:
            service = WorkflowService(lambda: config, registry, lambda: model, threading.BoundedSemaphore(1),
                                      'Use sources.', root=Path(root))
            try:
                run = service.start('Summarize budget', 'general')
                service.thread.join(8)
                result = service.detail(run['id'])
                self.assertEqual(result['error'], 'quota_exhausted')
                self.assertFalse(result['can_retry'])
                self.assertEqual(result['model_usage']['model_calls'], 1)
                self.assertEqual(len(model.calls), 1)
            finally:
                service.close()
