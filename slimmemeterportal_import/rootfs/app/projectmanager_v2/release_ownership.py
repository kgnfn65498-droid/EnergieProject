from __future__ import annotations
import hashlib,json,re,os
from pathlib import Path

VERSION_RE=re.compile(r'(?<!\d)(\d+\.\d+\.\d+)(?!\d)')

def _canon(record): return json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _sha(record): return hashlib.sha256(_canon(record)).hexdigest()

class LegacyOwnershipIndex:
    def __init__(self, project_root):
        self.path=Path(project_root)/'Inbox/projectmanager_v2/RuntimeV2/release_ownership/legacy_index.jsonl'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.parent.is_symlink() or not self.path.parent.is_dir():
            raise RuntimeError('legacy ownership directory is unsafe')
        self.path.parent.chmod(0o777)
    def _entries(self):
        if not self.path.exists(): return []
        out=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            try: v=json.loads(line)
            except Exception: continue
            if isinstance(v,dict): out.append(v)
        return out
    def classify(self, store, record, *, current_release):
        rid=str(record.get('id') or '')
        source_sha=_sha(record)
        for existing in reversed(self._entries()):
            if existing.get('store')==store and existing.get('record_id')==rid and existing.get('source_sha256')==source_sha:
                return existing
        text=' '.join(str(record.get(k) or '') for k in ('title','goal','next_action'))
        found=VERSION_RE.findall(text)
        if found and any(w in text.lower() for w in ('release','closure','maintenance','build','bouw')):
            status='MIGRATED'; scope='RELEASE'; owner=found[0]; lifecycle='RELEASE_TRANSIENT'
        else:
            status='LEGACY_AMBIGUOUS'; scope='EXTERNAL'; owner=None; lifecycle='LEGACY_REVIEW'
        entry={'store':store,'record_id':rid,'source_sha256':source_sha,'ownership_status':status,
               'scope':scope,'release_owner':owner,'lifecycle_class':lifecycle,'created_generation':'legacy','classification_evidence':found,'migration_version':'32.4.54-v1'}
        with self.path.open('a',encoding='utf-8') as h:
            h.write(json.dumps(entry,ensure_ascii=False,sort_keys=True)+'\n')
            h.flush()
            os.fsync(h.fileno())
        self.path.chmod(0o666)
        return entry
    def resolve(self, store, record):
        rid=str(record.get('id') or '')
        for e in reversed(self._entries()):
            if e.get('store')==store and e.get('record_id')==rid:
                if e.get('source_sha256')!=_sha(record): return {**e,'ownership_status':'LEGACY_AMBIGUOUS','scope':'EXTERNAL','release_owner':None}
                return e
        return {'ownership_status':'LEGACY_AMBIGUOUS','scope':'EXTERNAL','release_owner':None}
    def ownership(self, record, *, current_release):
        if record.get('scope') in {'RELEASE','GLOBAL','EXTERNAL'}:
            return {k:record.get(k) for k in ('scope','release_owner','lifecycle_class','created_generation')}
        return self.resolve('tasks',record)

def migrate_legacy_tasks(task_store, *, project_root, current_release: str, evidence_ref: str):
    idx=LegacyOwnershipIndex(project_root)
    current_tuple=tuple(int(x) for x in str(current_release).split('.'))
    classified=superseded=ambiguous=0
    for task in task_store.all():
        if task.get('scope') in {'RELEASE','GLOBAL','EXTERNAL'}:
            continue
        entry=idx.classify('tasks', task, current_release=current_release)
        classified += 1
        if entry.get('ownership_status') != 'MIGRATED' or entry.get('scope') != 'RELEASE':
            ambiguous += 1
            continue
        try: owner_tuple=tuple(int(x) for x in str(entry.get('release_owner') or '').split('.'))
        except ValueError:
            ambiguous += 1; continue
        if owner_tuple < current_tuple and task.get('status') not in {'DONE','SUPERSEDED'}:
            task_store.supersede(
                task['id'],
                reason=f"legacy release-owned task {entry.get('release_owner')} superseded by runtime {current_release}",
                evidence_refs=[str(evidence_ref)],
                superseded_by='release_ownership_migrator_v1',
            )
            superseded += 1
    return {'classified':classified,'superseded':superseded,'ambiguous':ambiguous}
