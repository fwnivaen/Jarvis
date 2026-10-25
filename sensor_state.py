"""Short-lived camera status and relief, independent of activity monitoring."""
import threading
import time

RELIEF_S = 180
SIGNAL_LEASE_S = 10
SIGNALS = ("eyes_active", "present", "head_down", "slouched")


class Sensors:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.signals = dict.fromkeys(SIGNALS, False)
        self.updated = float('-inf')
        self.quiet_until = 0

    def update(self, body):
        if not isinstance(body, dict) or any(type(body.get(key)) is not bool for key in SIGNALS):
            raise ValueError("Send boolean camera signals.")
        with self.lock:
            self.signals = {key: body[key] for key in SIGNALS}
            self.updated = self.clock()
            return self.state()

    def relief(self):
        with self.lock:
            self.quiet_until = self.clock() + RELIEF_S
            return self.state()

    def state(self):
        with self.lock:
            signals = self.signals if self.clock() - self.updated < SIGNAL_LEASE_S else dict.fromkeys(SIGNALS, False)
            return {**signals, "snooze_s": max(0, self.quiet_until - self.clock()), "paused": False}
