"""Identity boundary: labels are opt-in, transient samples; no titles or URLs are logged."""
import hashlib
import subprocess
from urllib.parse import urlsplit

HOST_LABELS = {'instagram.com': 'Instagram', 'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
    'x.com': 'X', 'twitter.com': 'X', 'reddit.com': 'Reddit', 'tiktok.com': 'TikTok',
    'netflix.com': 'Netflix', 'mail.google.com': 'Gmail', 'gmail.com': 'Gmail'}

def host_label(host):
    for domain, label in HOST_LABELS.items():
        if host == domain or host.endswith('.' + domain):
            return label
    return host.removeprefix('www.')


# Cold System Events reads can exceed 600ms while WebGL is busy. Keep a
# bounded deadline without converting an unavailable read into target credit.
QUERY_TIMEOUT_S = 1.2
SETTLE_TICKS = 2
HOME_PORT = 4700
HOME_HOSTS = frozenset({'localhost', '127.0.0.1'})
CHROME_IDS = frozenset({'com.google.Chrome', 'com.google.Chrome.beta', 'com.google.Chrome.dev',
    'com.google.Chrome.canary', 'org.chromium.Chromium', 'com.brave.Browser',
    'com.microsoft.edgemac', 'com.microsoft.edgemac.Beta', 'com.vivaldi.Vivaldi', 'company.thebrowser.Browser'})
OWN_IDS = frozenset({'JarvisFocusCard', 'JarvisVoice', 'com.jarvis.FocusCard', 'com.jarvis.Voice'})
FRONT_SCRIPT = '''tell application "System Events"
set p to first application process whose frontmost is true
if name of p is in {"JarvisFocusCard", "JarvisVoice"} then return name of p
return (bundle identifier of p) & linefeed & (name of p)
end tell'''
BROWSER_SCRIPT = 'tell application "System Events" to get bundle identifier of every application process whose background only is false'


class Reader:
    def __init__(self, query=None):
        self._query = query or self._osascript
        self._browser = None
        self._target = None
        self._candidate = None
        self._ticks = 0
        self._app_only = False

    @staticmethod
    def _osascript(script):
        result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True,
                                text=True, timeout=QUERY_TIMEOUT_S)
        if result.returncode:
            raise OSError('Activity permission unavailable')
        return result.stdout.strip()

    def clear(self):
        self._target = None
        self._candidate = None
        self._ticks = 0
        self._app_only = False

    def diagnostic(self):
        # A read-only probe: never arm, settle, or replace the real target.
        probe = Reader(self._query)
        probe._target = self._target
        probe.sample()
        return dict(probe._diag, settle_ticks=self._ticks,
                    app_target=self._target is not None,
                    tab_target=bool(self._target and self._target[1]))

    def sample(self, arm=False, settle=False, app_only=False, from_card=False, naming=False):
        self._diag = dict(front_readable=False, is_browser=False, tab_status='not_applicable',
                          front_is_jarvis=False, hash_present=False,
                          app_on_target=False, tab_on_target=False)
        try:
            # A new CLI process queries System Events EVERY sample. Never NSWorkspace notifications.
            front = self._query(FRONT_SCRIPT)
            bundle, _, app_name = front.partition('\n')
            label = app_name if naming else ''
            if not bundle:
                raise ValueError
            self._diag.update(front_readable=True, is_browser=bundle in CHROME_IDS)
            background = from_card or bundle in OWN_IDS
            if background:
                if bundle not in CHROME_IDS:
                    bundle = self._browser
                    if bundle is None:
                        running = self._query(BROWSER_SCRIPT).split(', ')
                        bundle = next((item for item in running if item in CHROME_IDS), None)
                if bundle not in CHROME_IDS:
                    raise ValueError
            if bundle in CHROME_IDS:
                self._browser = bundle
            self._diag['app_on_target'] = bool(self._target and bundle == self._target[0])
            host_hash, home = None, False
            if bundle in CHROME_IDS and not (app_only or self._app_only):
                script = f'''tell application id "{bundle}"
set focusedWindow to front window
set browserTitle to name of focusedWindow
set browserWindowID to id of focusedWindow
set focusedTab to active tab of focusedWindow
set surface to (URL of focusedTab) & linefeed & (browserWindowID as text) & linefeed & (id of focusedTab as text)
end tell
tell application "System Events"
set frontProcess to first application process whose frontmost is true
if bundle identifier of frontProcess is not "{bundle}" then error "Foreground changed"
set focusedTitle to name of (value of attribute "AXFocusedWindow" of frontProcess)
end tell
if focusedTitle is not browserTitle then error "Focused window unavailable"
return surface'''
                if background:
                    script = script.split('tell application "System Events"')[0] + 'return surface'
                self._diag['tab_status'] = 'unavailable'
                surface = self._query(script)
                url, window_id, tab_id = surface.rsplit('\n', 2)
                parsed = urlsplit(url)
                host = (parsed.hostname or '').lower().rstrip('.')
                if not url:
                    raise ValueError
                home = parsed.scheme == 'http' and host in HOME_HOSTS and parsed.port == HOME_PORT and parsed.path in ('/', '/index.html')
                label = host_label(host) if naming and parsed.scheme in ('http', 'https') and not home else ''
                host_hash = hashlib.sha256(f'{host}\n{window_id}\n{tab_id}'.encode()).digest()
            self._diag.update(tab_status='readable' if host_hash else 'not_applicable',
                              front_is_jarvis=home, hash_present=host_hash is not None)
            # Never scan other windows. Discard a read if foreground changed during scripting.
            if not background and self._query(FRONT_SCRIPT).partition('\n')[0] != bundle:
                raise ValueError
            identity = (bundle, host_hash)
            if arm:
                if home:
                    self._candidate, self._ticks = None, 0
                else:
                    self._ticks = self._ticks + 1 if self._candidate == identity else 1
                    self._candidate = identity
                    if not settle or self._ticks >= SETTLE_TICKS:
                        self._target = identity
                        self._app_only = app_only
            self._diag.update(app_on_target=bool(self._target and bundle == self._target[0]),
                              tab_on_target=bool(host_hash and identity == self._target))
            result = {'known': True, 'home': home, 'target': identity == self._target,
                      'locked': self._target is not None}
            if naming:
                result['label'] = label if not home and not background and identity != self._target else ''
            return result
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self._diag['tab_on_target'] = False
            if self._diag['tab_status'] == 'readable':
                self._diag.update(tab_status='foreground_changed', app_on_target=False, front_is_jarvis=False)
            self._candidate, self._ticks = None, 0
            return {'known': False, 'home': False, 'target': False, 'locked': self._target is not None}
