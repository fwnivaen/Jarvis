"""Isolated visual fixtures over the real viewer; no model calls or POST forwarding.

Run JARVIS first, then this file. View http://127.0.0.1:4702/?state=one
Only fixture activity is synthetic, visibly labelled; all production files stay intact.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = '127.0.0.1'
PORT = 4702
ORIGIN = 'http://127.0.0.1:4700'
PROXY_TIMEOUT_S = 5
FIXTURE_ID = '111111111111111111111111'
COUNTS = {'one': 1, 'two': 2, 'three': 3, 'review': 3, 'complete': 3}
LIMITS = {'max_workers': 3, 'worker_timeout_s': 45, 'request_timeout_s': 240, 'max_escalations': 1}


class Preview(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        cookies = SimpleCookie(self.headers.get('Cookie', ''))
        state = query.get('state', [cookies['visual-state'].value if 'visual-state' in cookies else 'one'])[0]
        if state not in COUNTS:
            state = 'one'
        path = urllib.parse.urlsplit(self.path).path
        code, mime = 200, 'application/json'
        if path == '/agents':
            data = {'enabled': True, 'crew_enabled': True, 'routing_enabled': False, 'agents': [], 'events': [],
                'active': False, 'elapsed_s': 0, 'limits': LIMITS}
            body = json.dumps(data).encode()
        elif path in ('/workflows', '/workflows/run'):
            agents = [{'slot': f'worker-{i+1}', 'status': 'complete' if state in ('review', 'complete') else 'running',
                'task': 'Visual fixture: analyzing a shared task', 'elapsed_s': 8, 'model': 'visual-fixture',
                'effort': 'high', 'attempts': 1, 'tokens': 0, 'usage_reported': False} for i in range(COUNTS[state])]
            if state == 'review':
                agents.append(dict(agents[0], slot='reviewer', status='running'))
            run = {'id': FIXTURE_ID, 'created_at': time.time()-8, 'elapsed_s': 8, 'tool_calls': 1,
                'status': 'complete' if state == 'complete' else 'running', 'agents': agents}
            data = run if path == '/workflows/run' else {'enabled': True, 'available': True, 'active': None if state == 'complete' else FIXTURE_ID, 'runs': [run]}
            body = json.dumps(data).encode()
        else:
            try:
                with urllib.request.urlopen(ORIGIN+self.path, timeout=PROXY_TIMEOUT_S) as response:
                    body, mime = response.read(), response.headers.get('Content-Type', 'application/octet-stream')
                if path == '/':
                    banner = '<nav style="position:fixed;z-index:100;bottom:8px;right:8px;max-width:calc(100vw - 16px);box-sizing:border-box;padding:8px;background:#14222b;color:#e6edf3;font:12px sans-serif;border:1px solid #79e4d5;border-radius:8px">VISUAL TEST · no agent execution &nbsp; '
                    banner += ' · '.join(f'<a style="color:#79e4d5" href="/?state={name}">{name}</a>' for name in COUNTS)+'</nav>'
                    body = body.replace(b'</body>', banner.encode()+b'</body>')
            except (urllib.error.URLError, TimeoutError):
                code, body, mime = 502, b'Run JARVIS on port 4700 first.', 'text/plain'
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Set-Cookie', f'visual-state={state}; SameSite=Strict; Path=/')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_error(405, 'Visual fixture server: no actions or inference permitted')


if __name__ == '__main__':
    print(f'Visual fixtures only: http://{HOST}:{PORT}/?state=one', flush=True)
    ThreadingHTTPServer((HOST, PORT), Preview).serve_forever()
