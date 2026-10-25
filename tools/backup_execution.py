"""Back up explicit SQLite stores; restore only to a new private directory.

Stop relevant services first. This never copies config, auth caches or notes.
The resulting databases contain selected task data; keep backups private.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3

PRIVATE_MODE=0o600


def snapshot(sources,destination):
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():raise ValueError('Destination must be new.')
    destination.mkdir(parents=True,mode=0o700)
    manifest={}
    for index,source in enumerate(sources):
        source=Path(source)
        if source.is_symlink() or not source.is_file() or source.suffix!='.sqlite':raise ValueError('Use explicit regular SQLite stores.')
        name=str(index)+'-'+source.name;target=destination/name
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_RDWR,PRIVATE_MODE);os.close(fd)
        with sqlite3.connect('file:'+str(source.resolve())+'?mode=ro',uri=True) as src,sqlite3.connect(target) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup integrity failed.')
        manifest[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    data=destination/'manifest.json';data.write_text(json.dumps(manifest,indent=2));os.chmod(data,PRIVATE_MODE)
    return manifest


def restore(backup,destination):
    backup=Path(backup);destination=Path(destination)
    manifest=json.loads((backup/'manifest.json').read_text())
    sources=[]
    for name,expected in manifest.items():
        if Path(name).name!=name or not name.endswith('.sqlite'):raise ValueError('Invalid backup manifest path.')
        source=backup/name
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('Backup checksum failed.')
        sources.append(source)
    return snapshot(sources,destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('backup','restore'));parser.add_argument('destination',type=Path)
    parser.add_argument('sources',nargs='+',type=Path);args=parser.parse_args()
    if args.action=='backup':result=snapshot(args.sources,args.destination)
    else:
        if len(args.sources)!=1:parser.error('Restore takes one backup directory.')
        result=restore(args.sources[0],args.destination)
    print('Verified SQLite stores:',len(result))
