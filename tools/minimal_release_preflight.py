from __future__ import annotations
import hashlib,json,stat,zipfile
from pathlib import Path

def _num(v):
    try:return tuple(int(x) for x in str(v).strip().split('.'))
    except Exception:return ()
def _sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def _safe(name):
    p=Path(name);return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name

def verify_candidate(root:Path,candidate:Path)->dict:
    root=Path(root);candidate=Path(candidate);blockers=[]
    incoming=root/'Inbox/incoming'
    items=sorted(p for p in incoming.glob('*.zip') if p.is_file() and not p.is_symlink()) if incoming.is_dir() else []
    if items!=[candidate]:blockers.append('incoming_not_exact_single_candidate')
    try:current=(root/'App/VERSIE.txt').read_text().strip()
    except Exception:current='';blockers.append('current_version_missing')
    version='';artifact_sha=''
    try:
        artifact_sha=_sha(candidate)
        with zipfile.ZipFile(candidate) as z:
            infos=z.infolist();names=[i.filename for i in infos]
            if len(names)!=len(set(names)) or z.testzip() is not None:raise RuntimeError()
            for i in infos:
                if not _safe(i.filename) or stat.S_ISLNK((i.external_attr>>16)&0o170000):raise RuntimeError()
            required={'VERSIE.txt','MANIFEST.sha256','SHA256SUMS.json'}
            if not required.issubset(names):raise RuntimeError()
            version=z.read('VERSIE.txt').decode().strip()
            manifest={}
            for line in z.read('MANIFEST.sha256').decode().splitlines():
                if not line.strip():continue
                sha,name=line.split(maxsplit=1);name=name.strip()
                if len(sha)!=64 or not _safe(name):raise RuntimeError()
                manifest[name]=sha.lower()
            sums=json.loads(z.read('SHA256SUMS.json').decode())
            sums={str(x['path']):str(x['sha256']).lower() for x in sums['files']}
            if manifest!=sums:raise RuntimeError()
            payload={i.filename for i in infos if not i.is_dir() and i.filename not in {'MANIFEST.sha256','SHA256SUMS.json'}}
            if payload!=set(manifest):raise RuntimeError()
            for name,sha in manifest.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=sha:raise RuntimeError()
    except Exception:blockers.append('candidate_integrity_invalid')
    if not current or not version or _num(version)<=_num(current):blockers.append('candidate_version_not_newer')
    rollback=root/f'App.__rollback_{current}' if current else root/'App.__rollback_unknown'
    candidate_dir=root/f'App.__candidate_{version}' if version else root/'App.__candidate_unknown'
    if rollback.exists():blockers.append('rollback_collision')
    if candidate_dir.exists():blockers.append('candidate_collision')
    return {'status':'GREEN' if not blockers else 'BLOCKED','ready':not blockers,'blockers':sorted(set(blockers)),
            'current_version':current,'candidate_version':version,'artifact_sha256':artifact_sha or None}
