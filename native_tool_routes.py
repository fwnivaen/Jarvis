"""Trusted local UI writes through the same bounded execution gateway.

The HTTP handler must validate local origin, feature switches and approval before
calling here. This registry is never exposed to models or MCP. Native note edits
and captures predate Ultra: disabling Ultra must not disable those controls.
"""
from pathlib import Path
import time

from execution_control import digest
from ultra_tools import Registry, ToolSession, spec

ROOT = Path(__file__).resolve().parent
JOURNAL_DIR = ROOT / '.local' / 'native-tools'
MAX_NATIVE_ARGUMENT_BYTES = 24 * 1024 * 1024
MAX_NATIVE_RESULT_CHARS = 16 * 1024 * 1024


class NativeRegistry(Registry):
    argument_limit = MAX_NATIVE_ARGUMENT_BYTES
    result_limit = MAX_NATIVE_RESULT_CHARS

    def __init__(self, name, properties, required, callback):
        super().__init__(None, {name: callback})
        self.declaration = spec(name, 'Explicit local viewer operation.', properties, required, write=True)

    def available(self):
        return [self.declaration]


def invoke(name, arguments, callback, *, properties, body, duration_s, root=None):
    """The request key is replay identity, not a remote authentication credential."""
    registry = NativeRegistry(name, properties, tuple(properties), callback)
    key = body.get('operation_session')
    session = ToolSession(registry, key, root=JOURNAL_DIR if root is None else root,
        permissions={name}, request_fingerprint=digest([name, body]) if key else None)
    try:
        return session.call(name, arguments, time.monotonic() + duration_s)
    finally:
        session.close()
