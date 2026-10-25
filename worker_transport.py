"""Authenticated private worker RPC, separate from the local viewer HTTP server."""
import base64
import hashlib
import hmac
import json
import math
import secrets
import ssl
import time
import urllib.request

from remote_workspaces import WorkspaceError,NoRedirect

MAX_RPC_BYTES=5*1024*1024
MAX_CLOCK_SKEW_S=30
RPC_TIMEOUT_S=15
MAX_NONCES=4096
MIN_KEY_CHARS=32
MIN_NONCE_CHARS=16
MAX_NONCE_CHARS=128
NONCE_BYTES=16


def signature(key,timestamp,nonce,raw):
    return hmac.new(key.encode(),timestamp.encode()+b'\n'+nonce.encode()+b'\n'+raw,hashlib.sha256).hexdigest()


class WorkerAuth:
    def __init__(self,manager,key,clock=time.time):
        if not isinstance(key,str) or len(key)<MIN_KEY_CHARS or key.startswith("OPERATOR_"):raise WorkspaceError('Private worker key required.')
        self.manager,self.key,self.clock=manager,key,clock
        with manager.db:manager.db.execute('CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY,expires REAL)')

    def verify(self,headers,raw):
        stamp=headers.get('X-Jarvis-Time','');nonce=headers.get('X-Jarvis-Nonce','');mac=headers.get('X-Jarvis-Signature','')
        try:timestamp=float(stamp)
        except ValueError:raise WorkspaceError('Worker authentication rejected.') from None
        if (not math.isfinite(timestamp) or len(raw)>MAX_RPC_BYTES or not MIN_NONCE_CHARS<=len(nonce)<=MAX_NONCE_CHARS or abs(self.clock()-timestamp)>MAX_CLOCK_SKEW_S
                or not hmac.compare_digest(mac,signature(self.key,stamp,nonce,raw))):
            raise WorkspaceError('Worker authentication rejected.')
        with self.manager.lock,self.manager.db:
            self.manager.db.execute('DELETE FROM nonces WHERE expires<?',(self.clock(),))
            if self.manager.db.execute('SELECT COUNT(*) FROM nonces').fetchone()[0]>=MAX_NONCES:raise WorkspaceError('Replay cache full.')
            try:self.manager.db.execute('INSERT INTO nonces VALUES (?,?)',(nonce,self.clock()+2*MAX_CLOCK_SKEW_S))
            except Exception:raise WorkspaceError('Worker request replay rejected.') from None


def dispatch(manager,body):
    """Called only AFTER worker authentication. No arbitrary commands or URL args."""
    if not isinstance(body,dict) or set(body)!={'operation','arguments'} or not isinstance(body['arguments'],dict):
        raise WorkspaceError('Invalid worker request.')
    operation,args=body['operation'],body['arguments']
    schemas={'create':{'key','run_id','worker_id','generation','expires_at'},'ready':{'wid'},
        'inspect':{'wid'},'destroy':{'wid'},'reconcile':set(),
        'action':{'wid','run_id','worker_id','generation','kind'},'watch':{'wid','run_id','worker_id','generation'}}
    if operation not in schemas or set(args)!=schemas[operation]:raise WorkspaceError('Invalid worker operation or schema.')
    if operation=='inspect':
        row=manager.get(args['wid'])
        return {k:v for k,v in row.items() if k!='endpoint'}
    result=getattr(manager,operation)(**args)
    if isinstance(result,bytes):return {'png':base64.b64encode(result).decode()}
    if isinstance(result,dict):return {k:v for k,v in result.items() if k!='endpoint'}
    return result


class WorkerClient:
    def __init__(self,url,key,*,ca_file,cert_file,key_file):
        # URL and certificates are operator configuration, never model arguments.
        if not url.startswith('https://') or '?' in url or '#' in url or '@' in url:raise WorkspaceError('Private HTTPS worker required.')
        self.url,self.key=url.rstrip('/'),key
        context=ssl.create_default_context(cafile=ca_file)
        context.load_cert_chain(cert_file,key_file)
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=context))

    def call(self,operation,arguments):
        raw=json.dumps({'operation':operation,'arguments':arguments},allow_nan=False).encode()
        stamp=str(time.time());nonce=secrets.token_hex(NONCE_BYTES)
        request=urllib.request.Request(self.url+'/rpc',data=raw,headers={'Content-Type':'application/json',
            'X-Jarvis-Time':stamp,'X-Jarvis-Nonce':nonce,'X-Jarvis-Signature':signature(self.key,stamp,nonce,raw)})
        try:
            with self.opener.open(request,timeout=RPC_TIMEOUT_S) as response:data=response.read(MAX_RPC_BYTES+1)
            if len(data)>MAX_RPC_BYTES:raise WorkspaceError('Worker response too large.')
            result=json.loads(data)
            if result.get('error'):raise WorkspaceError('Worker operation unconfirmed.')
            return result['result']
        except Exception:raise WorkspaceError('Worker unavailable or action uncertain; reconcile before retry.') from None
