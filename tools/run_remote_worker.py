"""Private fixture-only browser worker. Does not enable public or external browsing."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from remote_workspaces import WorkspaceManager
from worker_transport import WorkerAuth,dispatch,MAX_RPC_BYTES

PORT=7443
SOCKET_TIMEOUT_S=5


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--reap-once',action='store_true')
    args=parser.parse_args()
    if args.config.is_symlink() or args.config.stat().st_mode&0o077:raise SystemExit('Use a private regular worker configuration.')
    config=json.loads(args.config.read_text())
    manager=WorkspaceManager(config['state_path'])
    if args.reap_once:
        remaining=manager.reconcile()
        manager.close()
        raise SystemExit(bool(remaining))
    if config.get('fixture_only') is not True:raise SystemExit('External browser activation has not passed its gates.')
    auth=WorkerAuth(manager,config['worker_key'])
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_args):pass
        def setup(self):super().setup();self.connection.settimeout(SOCKET_TIMEOUT_S)
        def do_POST(self):
            try:
                if self.path!='/rpc' or self.headers.get('Origin') is not None:raise ValueError
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_RPC_BYTES:raise ValueError
                raw=self.rfile.read(length);auth.verify(self.headers,raw)
                result={'result':dispatch(manager,json.loads(raw))};status=200
            except Exception:result={'error':True};status=400
            data=json.dumps(result).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
    address=config.get('bind','127.0.0.1')
    http=ThreadingHTTPServer((address,config.get('port',PORT)),Handler)
    # Even private-network deployments require mutual TLS. No plaintext override.
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config['cert_file'],config['key_file'])
    context.load_verify_locations(config['ca_file']);context.verify_mode=ssl.CERT_REQUIRED
    http.socket=context.wrap_socket(http.socket,server_side=True)
    try:http.serve_forever()
    finally:http.server_close();manager.close()


if __name__=='__main__':main()
