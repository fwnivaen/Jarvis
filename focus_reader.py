"""Identity boundary: only booleans leave Reader; no titles or URLs are logged."""
import hashlib
import subprocess
from urllib.parse import urlsplit

QUERY_TIMEOUT_S = 0.6
HOME_PORT = 4700
HOME_HOSTS = frozenset({'localhost', '127.0.0.1'})
CHROME_IDS = frozenset({'com.google.Chrome', 'com.google.Chrome.beta', 'com.google.Chrome.dev',
    'com.google.Chrome.canary', 'org.chromium.Chromium', 'com.brave.Browser',
    'com.microsoft.edgemac', 'com.microsoft.edgemac.Beta', 'com.vivaldi.Vivaldi', 'company.thebrowser.Browser'})
FRONT_SCRIPT = 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true'


class Reader:
    def __init__(self, query=None):
        self._query = query or self._osascript
        self._target = None

    @staticmethod
    def _osascript(script):
        result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True,
                                text=True, timeout=QUERY_TIMEOUT_S)
        if result.returncode:
            raise OSError('Activity permission unavailable')
        return result.stdout.strip()

    def clear(self):
        self._target = None

    def sample(self, arm=False):
        try:
            # A new CLI process queries System Events EVERY sample. Never NSWorkspace notifications.
            bundle = self._query(FRONT_SCRIPT)
            if not bundle:
                raise ValueError
            host_hash, home = None, False
            if bundle in CHROME_IDS:
                url = self._query(f'tell application id "{bundle}" to get URL of active tab of front window')
                parsed = urlsplit(url)
                host = (parsed.hostname or '').lower().rstrip('.')
                if not url:
                    raise ValueError
                home = parsed.scheme == 'http' and host in HOME_HOSTS and parsed.port == HOME_PORT and parsed.path in ('/', '/index.html')
                host_hash = hashlib.sha256(host.encode()).digest()
            identity = (bundle, host_hash)
            if arm and not home:
                self._target = identity
            return {'known': True, 'home': home, 'target': identity == self._target,
                    'locked': self._target is not None}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'known': False, 'home': False, 'target': False, 'locked': self._target is not None}
