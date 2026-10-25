"""Stdlib browser worker lifecycle. Docker is accessible only to trusted operator code.

Initial provider uses an INTERNAL Docker network with no egress and no host mounts.
External navigation stays disabled until a separately verified egress policy exists.
Watch is a screenshot of the exact controlled WebDriver session, with no input API.
"""
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import urllib.request

IMAGE='selenium/standalone-chromium@sha256:c7c17cd79c62819a8329df00e610dbc4073c279da034a6f37135d454eb0d8870'
MAX_WORKSPACES=1
MAX_DURATION_S=300
MAX_ACTIONS=40
MAX_BYTES=4*1024*1024
MAX_DOWNLOAD_BYTES=8*1024*1024
MAX_VIEW_BYTES=2*1024*1024
MAX_CPU='1.0'
MAX_RAM='3g'
MAX_PIDS='512'
SHM_SIZE='1g'
DISK_SIZE='256m'
HTTP_TIMEOUT_S=5
DOCKER_TIMEOUT_S=10
SQL_TIMEOUT_S=5
ID_BYTES=12
MAX_LEASE_KEY_CHARS=128
MAX_URL_CHARS=2000
ID_RE=re.compile(rf'[a-f0-9]{{{ID_BYTES*2}}}\Z')
SESSION_RE=re.compile(r'[A-Za-z0-9-]{1,128}\Z')
LABEL='org.jarvis.workspace'
FIXTURE_HTML='<title>JARVIS synthetic browser fixture</title><h1 id="result">Workspace ready</h1>'


class WorkspaceError(ValueError):pass


def public_url(value,allowed_hosts,resolver=socket.getaddrinfo):
    """Validation alone is not egress enforcement. Provider still denies egress."""
    if not isinstance(value,str) or len(value)>MAX_URL_CHARS:raise WorkspaceError('Invalid URL.')
    url=urllib.parse.urlsplit(value)
    if (url.scheme!='https' or url.username or url.password or url.port not in (None,443)
            or not url.hostname or url.hostname.lower() not in allowed_hosts or url.fragment
            or any(c in value for c in ('\\','\r','\n','\t'))):
        raise WorkspaceError('URL outside navigation scope.')
    try:addresses=resolver(url.hostname,443,type=socket.SOCK_STREAM)
    except OSError:raise WorkspaceError('DNS unavailable.') from None
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise WorkspaceError('Private or metadata destination denied.')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):return None


class DockerBrowser:
    """No arbitrary commands/arguments from models. Fixed resource/network policy."""
    def command(self,*args):
        result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=DOCKER_TIMEOUT_S)
        if result.returncode:raise WorkspaceError('Docker operation failed; inspect privately.')
        return result.stdout.strip()

    def create(self,workspace):
        wid=workspace['id'];network='jarvis-'+wid
        self.command('network','create','--internal','--label',LABEL+'='+wid,network)
        try:
            # A worker-owned timer survives RPC/controller/client disconnection.
            # Production requires systemd and operator-installed Docker on Linux.
            duration=max(1,int(workspace['expires_at']-time.time()))
            timer=subprocess.run(['systemd-run','--unit','jarvis-expiry-'+wid,
                '--on-active='+str(duration)+'s','--timer-property=AccuracySec=1s',
                '/usr/bin/docker','rm','--force','jarvis-'+wid],
                capture_output=True,timeout=DOCKER_TIMEOUT_S)
            if timer.returncode:raise WorkspaceError('Independent hard-expiry timer unavailable.')
            self.command('run','--detach','--name','jarvis-'+wid,'--label',LABEL+'='+wid,
                '--label','org.jarvis.expires='+str(workspace['expires_at']),
                '--network',network,'--publish','127.0.0.1::4444',
                '--memory',MAX_RAM,'--memory-swap',MAX_RAM,'--cpus',MAX_CPU,'--pids-limit',MAX_PIDS,
                '--shm-size',SHM_SIZE,'--cap-drop','ALL','--security-opt','no-new-privileges',
                '--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size='+DISK_SIZE,
                '--tmpfs','/home/seluser:rw,nosuid,size='+DISK_SIZE+',uid=1200,gid=1201',
                '--log-driver','none','--env','SE_ENABLE_TRACING=false','--env','SE_VNC_VIEW_ONLY=true',
                '--env','SE_START_VNC=false','--env','SE_START_NO_VNC=false',
                '--env','SE_NODE_MAX_SESSIONS=1','--env','SE_NODE_SESSION_TIMEOUT='+str(MAX_DURATION_S),IMAGE)
            value=self.inspect(wid)
            return {'endpoint':value['endpoint']}
        except Exception:
            # Failed cleanup is retried by manager/reaper, not declared successful.
            raise

    def inspect(self,wid):
        if not ID_RE.fullmatch(wid):raise WorkspaceError('Invalid workspace.')
        data=json.loads(self.command('inspect','jarvis-'+wid))[0]
        if data['Config']['Labels'].get(LABEL)!=wid:raise WorkspaceError('Container ownership mismatch.')
        binding=data['NetworkSettings']['Ports'].get('4444/tcp')
        if not binding or len(binding)!=1 or binding[0]['HostIp']!='127.0.0.1':raise WorkspaceError('Unsafe browser endpoint.')
        return {'running':data['State']['Running'],'endpoint':'http://127.0.0.1:'+binding[0]['HostPort']}

    def destroy(self,wid):
        if not ID_RE.fullmatch(wid):raise WorkspaceError('Invalid workspace.')
        names=self.command('ps','-aq','--filter','label='+LABEL+'='+wid)
        if names:self.command('rm','--force','jarvis-'+wid)
        remaining=self.command('ps','-aq','--filter','label='+LABEL+'='+wid)
        if remaining:raise WorkspaceError('Container cleanup unconfirmed.')
        networks=self.command('network','ls','-q','--filter','label='+LABEL+'='+wid)
        if networks:self.command('network','rm','jarvis-'+wid)
        if self.command('network','ls','-q','--filter','label='+LABEL+'='+wid):raise WorkspaceError('Network cleanup unconfirmed.')
        return True

    def inventory(self):
        ids=self.command('ps','-aq','--filter','label='+LABEL).splitlines()
        if not ids:return []
        data=json.loads(self.command('inspect',*ids))
        return [{'id':x['Config']['Labels'].get(LABEL),'expires_at':float(x['Config']['Labels'].get('org.jarvis.expires','0'))}
                for x in data]

    def webdriver(self,workspace,method,path,body=None):
        endpoint=self.inspect(workspace['id'])['endpoint']
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        request=urllib.request.Request(endpoint+path,method=method,
            data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with opener.open(request,timeout=HTTP_TIMEOUT_S) as response:raw=response.read(MAX_BYTES+1)
        except Exception:raise WorkspaceError('WebDriver unavailable or unsettled.') from None
        if len(raw)>MAX_BYTES:raise WorkspaceError('Browser response too large.')
        value=json.loads(raw)['value']
        if isinstance(value,dict) and value.get('error'):raise WorkspaceError('Browser action failed.')
        return value


class WorkspaceManager:
    def __init__(self,path,provider=None,clock=time.time):
        self.path,self.clock=Path(path),clock
        self.provider=provider or DockerBrowser()
        if self.path.is_symlink() or self.path.parent.is_symlink():raise WorkspaceError('Unsafe workspace store.')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.path.parent,0o700)
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.fchmod(fd,0o600);os.close(fd)
        self.db=sqlite3.connect(self.path,timeout=SQL_TIMEOUT_S,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, request_key TEXT UNIQUE, data TEXT)')
        self.lock=threading.RLock()

    def _save(self,row):
        with self.db:self.db.execute('UPDATE workspaces SET data=? WHERE id=?',(json.dumps(row,allow_nan=False),row['id']))

    def get(self,wid):
        with self.lock:
            found=self.db.execute('SELECT data FROM workspaces WHERE id=?',(wid,)).fetchone()
            if found is None:raise WorkspaceError('Unknown workspace.')
            return json.loads(found[0])

    def create(self,key,*,run_id,worker_id,generation,expires_at):
        if (not all(isinstance(x,str) and ID_RE.fullmatch(x) for x in (run_id,worker_id))
                or type(generation) is not int or generation<1 or not self.clock()<expires_at<=self.clock()+MAX_DURATION_S
                or not isinstance(key,str) or not 0<len(key)<=MAX_LEASE_KEY_CHARS):raise WorkspaceError('Invalid workspace lease.')
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                saved=self.db.execute('SELECT data FROM workspaces WHERE request_key=?',(key,)).fetchone()
                if saved:
                    row=json.loads(saved[0])
                    if any(row[k]!=v for k,v in {'run_id':run_id,'worker_id':worker_id,'generation':generation,'expires_at':expires_at}.items()):
                        raise WorkspaceError('Workspace request key reused.')
                    self.db.commit();return row
                all_rows=[json.loads(x[0]) for x in self.db.execute('SELECT data FROM workspaces')]
                if sum(x['state']!='destroyed' for x in all_rows)>=MAX_WORKSPACES:raise WorkspaceError('Browser capacity occupied; queue this task.')
                row={'id':secrets.token_hex(ID_BYTES),'run_id':run_id,'worker_id':worker_id,'generation':generation,
                    'expires_at':expires_at,'state':'creating','cleanup':'none','actions':0,'session':None,'action_state':'idle','artifacts':[]}
                self.db.execute('INSERT INTO workspaces VALUES (?,?,?)',(row['id'],key,json.dumps(row)))
                self.db.commit()
            except BaseException:self.db.rollback();raise
            try:
                row.update(self.provider.create(row));row['state']='starting';self._save(row)
            except Exception:
                row.update(state='failed',cleanup='pending');self._save(row)
                raise WorkspaceError('Workspace creation failed; cleanup pending.') from None
            return row

    def ready(self,wid):
        with self.lock:
            row=self.get(wid)
            if row['state']=='ready':return row
            if row['state']!='starting' or row['action_state']!='idle' or self.clock()>=row['expires_at']:raise WorkspaceError('Workspace not starting or expired.')
            status=self.provider.webdriver(row,'GET','/status')
            if not status.get('ready'):raise WorkspaceError('Browser not ready yet.')
            # Persist creating session before request; failure leaves uncertainty.
            row['action_state']='session_pending';self._save(row)
            value=self.provider.webdriver(row,'POST','/session',{'capabilities':{'alwaysMatch':{
                'browserName':'chrome','goog:chromeOptions':{'args':['--disable-file-system','--disable-extensions',
                    '--disable-background-networking','--disable-sync','--no-first-run'],
                    'prefs':{'download_restrictions':3,'download.prompt_for_download':True}}}}})
            session=value.get('sessionId')
            if not isinstance(session,str) or not SESSION_RE.fullmatch(session):raise WorkspaceError('Invalid session identity.')
            row.update(session=session,state='ready',action_state='idle');self._save(row)
            return row

    def _lease(self,row,run_id,worker_id,generation):
        if (row['run_id']!=run_id or row['worker_id']!=worker_id or row['generation']!=generation
                or self.clock()>=row['expires_at'] or row['state']!='ready'):
            raise WorkspaceError('Workspace lease expired, fenced or outside owner.')

    def action(self,wid,*,run_id,worker_id,generation,kind,value=None):
        with self.lock:
            row=self.get(wid);self._lease(row,run_id,worker_id,generation)
            if row['actions']>=MAX_ACTIONS or row['action_state']!='idle':raise WorkspaceError('Action budget or unresolved action.')
            # Safe initial scope: there is no element-input or arbitrary script API.
            # Egress is denied by INTERNAL network; no allowlist-only security claim.
            if kind=='fixture':method,path,body='POST','/url',{'url':'data:text/html,'+urllib.parse.quote(FIXTURE_HTML)}
            elif kind=='screenshot':method,path,body='GET','/screenshot',None
            elif kind=='inspect':method,path,body='GET','/title',None
            else:raise WorkspaceError('Action unavailable pending network/input acceptance gates.')
            row['actions']+=1;row['action_state']='pending';self._save(row)
            result=self.provider.webdriver(row,method,'/session/'+row['session']+path,body)
            self._lease(row,run_id,worker_id,generation)
            row['action_state']='idle';self._save(row)
            if kind=='screenshot':
                try:data=base64.b64decode(result,validate=True)
                except Exception:raise WorkspaceError('Invalid screenshot.') from None
                if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)>MAX_VIEW_BYTES:raise WorkspaceError('Invalid screenshot size or type.')
                return data
            return result

    def watch(self,wid,**lease):
        """Read-only exact-session capture. No VNC socket or human input channel."""
        return self.action(wid,kind='screenshot',**lease)

    def destroy(self,wid):
        with self.lock:
            row=self.get(wid)
            if row['state']=='destroyed':return row
            row.update(state='stopping',generation=row['generation']+1,cleanup='pending');self._save(row)
            session_deleted=not row.get('session')
            if row.get('session'):
                try:self.provider.webdriver(row,'DELETE','/session/'+row['session']);session_deleted=True
                except Exception:pass
            try:terminated=self.provider.destroy(wid)
            except Exception:terminated=False
            # Container death implies its in-memory WebDriver session is gone.
            if terminated:
                row.update(state='destroyed',cleanup='complete',session_deleted=True,container_terminated=True)
            else:
                row.update(session_deleted=session_deleted,container_terminated=False)
            self._save(row);return row

    def reconcile(self):
        with self.lock:
            known={x[0] for x in self.db.execute('SELECT id FROM workspaces')}
            for wid in known:
                row=self.get(wid)
                if row['state']!='destroyed' and (row['expires_at']<=self.clock() or row['cleanup']=='pending'):
                    self.destroy(wid)
            # Independent reaper also catches create-before-persist crashes.
            for container in self.provider.inventory():
                if container['id'] not in known or container['expires_at']<=self.clock():
                    try:self.provider.destroy(container['id'])
                    except Exception:pass  # Caller must inspect inventory again; never claim zero leaks here.
            return self.provider.inventory()

    def close(self):self.db.close()
