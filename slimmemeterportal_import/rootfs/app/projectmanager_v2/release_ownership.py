from __future__ import annotations
from system_path_contract import project_system_path
import hashlib,json,re,os,stat
from pathlib import Path

VERSION_RE=re.compile(r'(?<!\d)(\d+\.\d+\.\d+)(?!\d)')

def _canon(record): return json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _sha(record): return hashlib.sha256(_canon(record)).hexdigest()

class LegacyOwnershipIndex:
    """One streaming index load per instance; classify/resolve are O(1) lookups afterwards."""
    def __init__(self, project_root):
        self.path=project_system_path(Path(project_root), 'Inbox/projectmanager_v2/RuntimeV2/release_ownership/legacy_index.jsonl')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.parent.is_symlink() or not self.path.parent.is_dir():
            raise RuntimeError('legacy ownership directory is unsafe')
        self.path.parent.chmod(0o777)
        self._loaded=False
        self._by_exact={}
        self._latest={}
        self.load_passes=0

    def _load_once(self):
        if self._loaded:return
        self._loaded=True;self.load_passes+=1
        try:st=self.path.lstat()
        except FileNotFoundError:return
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RuntimeError('legacy ownership index is unsafe')
        with self.path.open('r',encoding='utf-8') as h:
            for line in h:
                try:v=json.loads(line)
                except Exception:continue
                if not isinstance(v,dict):continue
                store=str(v.get('store') or '');rid=str(v.get('record_id') or '');source=str(v.get('source_sha256') or '')
                if not store or not rid:continue
                self._latest[(store,rid)]=v
                if source:self._by_exact[(store,rid,source)]=v

    def _append(self,entry):
        self._load_once()
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        if hasattr(os,'O_NOFOLLOW'):flags|=os.O_NOFOLLOW
        fd=os.open(str(self.path),flags,0o666)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):raise RuntimeError('legacy ownership index is not regular')
            os.fchmod(fd,0o666)
            with os.fdopen(fd,'a',encoding='utf-8',closefd=False) as h:
                h.write(json.dumps(entry,ensure_ascii=False,sort_keys=True)+'\n')
                h.flush();os.fsync(h.fileno())
        finally:
            os.close(fd)
        store=str(entry.get('store') or '');rid=str(entry.get('record_id') or '');source=str(entry.get('source_sha256') or '')
        self._latest[(store,rid)]=entry
        if source:self._by_exact[(store,rid,source)]=entry

    def classify(self, store, record, *, current_release):
        self._load_once()
        rid=str(record.get('id') or '')
        source_sha=_sha(record)
        existing=self._by_exact.get((str(store),rid,source_sha))
        if existing is not None:return existing
        text=' '.join(str(record.get(k) or '') for k in ('title','goal','next_action'))
        found=VERSION_RE.findall(text)
        if found and any(w in text.lower() for w in ('release','closure','maintenance','build','bouw')):
            status='MIGRATED'; scope='RELEASE'; owner=found[0]; lifecycle='RELEASE_TRANSIENT'
        else:
            status='LEGACY_AMBIGUOUS'; scope='EXTERNAL'; owner=None; lifecycle='LEGACY_REVIEW'
        entry={'store':store,'record_id':rid,'source_sha256':source_sha,'ownership_status':status,
               'scope':scope,'release_owner':owner,'lifecycle_class':lifecycle,'created_generation':'legacy',
               'classification_evidence':found,'migration_version':'32.4.57-v2'}
        self._append(entry)
        return entry

    def resolve(self, store, record):
        self._load_once()
        rid=str(record.get('id') or '')
        e=self._latest.get((str(store),rid))
        if e is not None:
            if e.get('source_sha256')!=_sha(record):
                return {**e,'ownership_status':'LEGACY_AMBIGUOUS','scope':'EXTERNAL','release_owner':None}
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
        entry=idx.classify('tasks',task,current_release=current_release)
        classified+=1
        if entry.get('ownership_status')!='MIGRATED' or entry.get('scope')!='RELEASE':
            ambiguous+=1;continue
        try:owner_tuple=tuple(int(x) for x in str(entry.get('release_owner') or '').split('.'))
        except ValueError:
            ambiguous+=1;continue
        if owner_tuple<current_tuple and task.get('status') not in {'DONE','SUPERSEDED'}:
            task_store.supersede(
                task['id'],
                reason=f"legacy release-owned task {entry.get('release_owner')} superseded by runtime {current_release}",
                evidence_refs=[str(evidence_ref)],
                superseded_by='release_ownership_migrator_v2',
            )
            superseded+=1
    return {'classified':classified,'superseded':superseded,'ambiguous':ambiguous,'legacy_index_load_passes':idx.load_passes}
