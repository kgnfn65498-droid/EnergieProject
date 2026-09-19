from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path
from release_controller import Outcome,ReleaseState

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def _json(path):
    try:v=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return {}
    return v if isinstance(v,dict) else {}
def _atomic(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('unsafe publication marker')
    tmp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    try:tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

class HADelivery:
    def __init__(self,root:Path,*,timeout_seconds=600):self.root=Path(root);self.timeout=float(timeout_seconds)
    def _processed(self,s):
        src=self.root/'Inbox/processing'/s.artifact_name;dst=self.root/'Inbox/processed'/s.artifact_name
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.is_file():
            if _sha(dst)!=s.artifact_sha256:raise RuntimeError('processed_artifact_hash_conflict')
            if src.is_file() and _sha(src)==s.artifact_sha256:src.unlink()
            return dst
        if not src.is_file():raise RuntimeError('processing_artifact_missing')
        if _sha(src)!=s.artifact_sha256:raise RuntimeError('processing_artifact_hash_mismatch')
        os.replace(src,dst);return dst
    def _manifest_sha(self,p):
        if not Path(p).is_file():raise RuntimeError('manifest_missing')
        return _sha(Path(p))
    def _contract(self,s,processed):
        rollback=self.root/f'App.__rollback_{s.from_version}'
        return {'status':'publication_required','version':s.to_version,
            'repository':'https://github.com/kgnfn65498-droid/EnergieProject','branch':'main',
            'expected_previous_version':s.from_version,
            'expected_previous_manifest_sha256':self._manifest_sha(rollback/'MANIFEST.sha256'),
            'target_manifest_sha256':self._manifest_sha(self.root/'App/MANIFEST.sha256'),
            'processed_zip':processed.name,'processed_zip_sha256':s.artifact_sha256,
            'release_id':s.release_id,'generation':s.generation}
    def align(self,s:ReleaseState)->Outcome:
        try:
            processed=self._processed(s);payload=self._contract(s,processed);marker=self.root/'Inbox/ha_publication_required.json'
            existing=_json(marker)
            if existing:
                core_keys=(
                    'status','version','repository','branch','expected_previous_version',
                    'expected_previous_manifest_sha256','target_manifest_sha256',
                    'processed_zip','processed_zip_sha256'
                )
                if any(existing.get(k)!=payload.get(k) for k in core_keys):
                    return Outcome.blocked('publication_contract_conflict','inspect existing publication contract')
                old_release_id=existing.get('release_id')
                old_generation=existing.get('generation')
                if old_release_id not in (None,'',s.release_id) or old_generation not in (None,'',s.generation):
                    return Outcome.blocked('publication_contract_fence_conflict','inspect existing publication contract')
                if old_release_id!=s.release_id or old_generation!=s.generation:
                    merged=dict(existing);merged['release_id']=s.release_id;merged['generation']=s.generation
                    _atomic(marker,merged)
            else:_atomic(marker,payload)
        except Exception as exc:return Outcome.blocked(str(exc))
        ha=_json(self.root/'Inbox/ha_runtime/current.json')
        if str(ha.get('version') or '')==s.to_version:return Outcome.green('processed_archived','ha_runtime_current')
        pub=_json(self.root/'Inbox/github_publication_state.json')
        elapsed=max(0.0,time.time()-float(s.phase_started_at_epoch or time.time()))
        if elapsed>=self.timeout:
            reason='github_publication_failed' if pub.get('published') is False and str(pub.get('version') or '')==s.to_version else 'ha_runtime_alignment_timeout'
            return Outcome.blocked(reason,'inspect existing publisher/runtime evidence; do not create a second release')
        if pub.get('published') is True and str(pub.get('version') or '')==s.to_version:
            return Outcome.waiting('ha_runtime_start_pending','github_target_published','processed_archived')
        return Outcome.waiting('github_publication_pending','publication_contract_ready','processed_archived')
