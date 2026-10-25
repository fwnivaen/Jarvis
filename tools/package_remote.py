"""Package source by allowlist. Never include notes, config, caches, profiles or state."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ALLOW_ROOT={'server.py','build.py','focus.py','focus_reader.py','watch.py','voice_bridge.py','note_store.py',
 'ultra.py','ultra_tools.py','ultra_memory.py','ultra_documents.py','ultra_monitor.py','ultra_workflows.py',
 'codex_bridge.py','workflow_graph.py','workflow_runtime.py','execution_control.py','execution_gateway.py',
 'execution_scheduler.py','execution_adapters.py','helper_protocol.py','remote_workspaces.py','worker_transport.py',
 'learning_gate.py','outcome_collection.py','execution_evaluation.py','native_tool_routes.py','requirements-ultra.txt','THIRD_PARTY.md'}
ALLOW_TREES={'viewer','optional','dependencies','deploy'}
ALLOW_TOOLS={'run_remote_controller.py','run_remote_worker.py','setup_execution.py','backup_execution.py'}
EXCLUDED={'graph-data.js','config.json','.env','.DS_Store','__pycache__'}
MAX_PACKAGE_BYTES=100*1024*1024


def selected():
    # Only reviewed indexed files can enter a deployment artifact. Untracked
    # private files anywhere under optional/deploy/viewer are excluded as well.
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for name in sorted(filter(None,names)):
        rel=Path(name);path=ROOT/rel
        if path.is_symlink() or not path.is_file() or set(rel.parts)&EXCLUDED or path.suffix in {'.pyc','.key','.pem','.p12'}:continue
        if (len(rel.parts)==1 and rel.name in ALLOW_ROOT or rel.parts[0] in ALLOW_TREES
                or len(rel.parts)>2 and rel.parts[:2]==('docs','licenses')
                or rel.parts[0]=='tools' and rel.name in ALLOW_TOOLS):yield path,rel.as_posix()


def package(destination):
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():raise ValueError('Use a new package destination.')
    files=list(selected())
    if sum(p.stat().st_size for p,_ in files)>MAX_PACKAGE_BYTES:raise ValueError('Source package exceeds limit.')
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for path,name in files}
    with tarfile.open(destination,'x:gz') as archive:
        for path,name in files:
            info=archive.gettarinfo(str(path),arcname='jarvis/'+name);info.uid=info.gid=0;info.uname=info.gname=''
            archive.addfile(info,io.BytesIO(path.read_bytes()))
        data=json.dumps(manifest,sort_keys=True,indent=2).encode()
        info=tarfile.TarInfo('jarvis/SOURCE-MANIFEST.json');info.size=len(data);info.mode=0o644
        archive.addfile(info,io.BytesIO(data))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    print('Source files packaged:',len(package(args.output)))
