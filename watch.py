"""Local screen-watch indicator lease. No pixels or text are accepted here."""
import re
import subprocess
import threading
import time
from pathlib import Path

LEASE_S = 15
CARD = Path(__file__).resolve().parent / '.local' / 'JarvisWatchCard'
TOKEN = re.compile(r'^[a-zA-Z0-9-]{16,64}$')

class Watch:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.sessions = {}
        self.process = None
        self.lock = threading.RLock()

    def state(self):
        with self.lock:
            self.sessions = {k:v for k,v in self.sessions.items() if v > self.clock()}
            return {'active': bool(self.sessions), 'card': self.process is not None and self.process.poll() is None}

    def update(self, body):
        if set(body) != {'token', 'active'} or not isinstance(body['token'], str) or not TOKEN.fullmatch(body['token']) or type(body['active']) is not bool:
            raise ValueError('Watch accepts only a session token and active boolean.')
        with self.lock:
            if body['active']:
                self.sessions[body['token']] = self.clock() + LEASE_S
                if (self.process is None or self.process.poll() is not None) and CARD.is_file():
                    self.process = subprocess.Popen([str(CARD)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                self.sessions.pop(body['token'], None)
            return self.state()
