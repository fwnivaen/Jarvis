"""Authenticated bounded gateway for optional execution adapters; no SDK imports."""
import threading
import time

from execution_control import ControlError, digest, identifier

CLASSIFICATIONS = {'notes_search': 'observation', 'note_read': 'observation',
    'preferences_get': 'observation', 'focus_status': 'observation', 'screen_watch_status': 'observation',
    'notes_capture': 'reversible', 'note_write': 'reversible', 'preferences_set': 'reversible',
    'preferences_forget': 'reversible', 'document_import': 'reversible',
    'focus_control': 'reversible', 'screen_watch_control': 'reversible'}


class ToolGateway:
    def __init__(self, store, registry):
        self.store, self.registry = store, registry
        self.lock = threading.RLock()

    def catalog(self, token, run_id):
        actor = self.store.authenticate(token, run_id)
        return [item for item in self.registry.dynamic_specs() if item['name'] in actor['permissions']]

    def call(self, token, run_id, operation_id, name, arguments, *, deadline, cancel=None):
        # The registry validates schema and feature gates before durable reservation.
        self.registry.lookup(name, arguments)
        if time.monotonic() >= deadline or cancel is not None and cancel.is_set():
            raise ControlError('Tool cancelled or expired.')
        classification = CLASSIFICATIONS.get(name)
        if classification is None:
            raise ControlError('Unclassified tool unavailable.')
        with self.lock:
            operation, cached = self.store.reserve(token, run_id, operation_id, name, arguments, classification)
            if cached:
                return {'result': operation['result'], 'receipt': {'operation_id': operation_id,
                    'result_hash': digest(operation['result']), 'generation': operation['generation']}}
            # Cancellation must fence the store generation before acknowledging Stop.
            self.store.authenticate(token, run_id)
            result = self.registry.call(name, arguments, deadline=deadline)
            if time.monotonic() >= deadline or cancel is not None and cancel.is_set():
                raise ControlError('Unsettled tool after cancellation or deadline.')
            receipt = self.store.settle(token, run_id, operation_id, result)
            return {'result': result, 'receipt': receipt}

    def invoke(self, token, run_id, name, arguments, deadline, cancel=None):
        """Executor owns IDs; writers use stable request IDs, never model-selected IDs."""
        item = self.registry.lookup(name, arguments)
        op_id = digest([name, arguments]) if item['write'] else identifier()
        return self.call(token, run_id, op_id, name, arguments, deadline=deadline, cancel=cancel)['result']
