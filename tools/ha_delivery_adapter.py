from __future__ import annotations
import hashlib,json,os,time,zipfile
from pathlib import Path
from release_controller import Outcome,ReleaseState

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def _json(path):
    try:
        p=Path(path)
        if p.is_symlink() or not p.is_file(): return {}
        v=json.loads(p.read_text(encoding='utf-8'))
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
    def _active_artifact(self,s):
        processing=self.root/'Inbox/processing'/s.artifact_name
        processed=self.root/'Inbox/processed'/s.artifact_name
        if processing.is_file() and not processing.is_symlink():
            if _sha(processing)!=s.artifact_sha256:raise RuntimeError('processing_artifact_hash_mismatch')
            return processing
        # Crash reconciliation: delivery may have archived immediately before
        # controller state reached COMPLETE. Only exact owned artifact is valid.
        if processed.is_file() and not processed.is_symlink():
            if _sha(processed)!=s.artifact_sha256:raise RuntimeError('processed_artifact_hash_conflict')
            return processed
        raise RuntimeError('owned_artifact_missing')
    def _archive_complete(self,s):
        src=self.root/'Inbox/processing'/s.artifact_name;dst=self.root/'Inbox/processed'/s.artifact_name
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.is_file():
            if dst.is_symlink() or _sha(dst)!=s.artifact_sha256:raise RuntimeError('processed_artifact_hash_conflict')
            if src.is_file():
                if src.is_symlink() or _sha(src)!=s.artifact_sha256:raise RuntimeError('processing_artifact_hash_mismatch')
                src.unlink()
            return dst
        if src.is_symlink() or not src.is_file():raise RuntimeError('processing_artifact_missing')
        if _sha(src)!=s.artifact_sha256:raise RuntimeError('processing_artifact_hash_mismatch')
        os.replace(src,dst)
        if not dst.is_file() or dst.is_symlink() or _sha(dst)!=s.artifact_sha256:raise RuntimeError('processed_archive_readback_failed')
        return dst
    def _manifest_sha(self,p):
        if not Path(p).is_file():raise RuntimeError('manifest_missing')
        return _sha(Path(p))
    def _target_manifest_sha(self,artifact):
        try:
            with zipfile.ZipFile(artifact) as archive:
                return hashlib.sha256(archive.read('MANIFEST.sha256')).hexdigest()
        except Exception as exc:raise RuntimeError('target_manifest_missing_or_invalid') from exc
    def _pre_target_contract(self,s,artifact):
        active=self.root/'App'
        active_version=(active/'VERSIE.txt').read_text(encoding='utf-8').strip() if (active/'VERSIE.txt').is_file() else ''
        predecessor=active if active_version==s.from_version else self.root/f'App.__rollback_{s.from_version}'
        previous_manifest=self._manifest_sha(predecessor/'MANIFEST.sha256')
        return {'schema':'energie_ha_publication_contract_v2','status':'publication_required',
            'source_stage':'processing_pre_target','version':s.to_version,
            'repository':'https://github.com/kgnfn65498-droid/EnergieProject','branch':'main',
            'expected_previous_version':s.from_version,'expected_previous_manifest_sha256':previous_manifest,
            'predecessor_version':s.from_version,'predecessor_manifest_sha256':previous_manifest,
            'target_manifest_sha256':self._target_manifest_sha(artifact),
            'processed_zip':artifact.name,'processed_zip_sha256':s.artifact_sha256,
            'release_id':s.release_id,'generation':s.generation}
    def _contract(self,s,artifact):
        rollback=self.root/f'App.__rollback_{s.from_version}'
        return {'schema':'energie_ha_publication_contract_v2','status':'publication_required','version':s.to_version,
            'repository':'https://github.com/kgnfn65498-droid/EnergieProject','branch':'main',
            'expected_previous_version':s.from_version,
            'expected_previous_manifest_sha256':self._manifest_sha(rollback/'MANIFEST.sha256'),
            'target_manifest_sha256':self._manifest_sha(self.root/'App/MANIFEST.sha256'),
            'processed_zip':artifact.name,'processed_zip_sha256':s.artifact_sha256,
            'release_id':s.release_id,'generation':s.generation}
    @staticmethod
    def _identity_matches(payload,expected):
        keys=('version','release_id','generation','processed_zip','processed_zip_sha256','target_manifest_sha256')
        return all(str(payload.get(k) or '')==str(expected.get(k) or '') for k in keys)
    def _ensure_contract(self,s,payload,marker):
        existing=_json(marker)
        if not existing:
            _atomic(marker,payload);return payload
        core=('source_stage','version','repository','branch','expected_previous_version','expected_previous_manifest_sha256','predecessor_version','predecessor_manifest_sha256','target_manifest_sha256','processed_zip','processed_zip_sha256')
        if any(existing.get(k)!=payload.get(k) for k in core):raise RuntimeError('publication_contract_conflict')
        if str(existing.get('release_id') or '')!=s.release_id or str(existing.get('generation') or '')!=s.generation:
            raise RuntimeError('publication_contract_fence_conflict')
        return existing
    def _publisher_exact(self,pub,payload):
        return bool(pub.get('published') is True and pub.get('target_exact') is True and pub.get('remote_head') and self._identity_matches(pub,payload))
    def reconcile_completed_delivery(self,s:ReleaseState)->Outcome:
        marker=self.root/'Inbox/ha_publication_required.json'
        if not marker.exists(): return Outcome.green('completed_delivery_settled')
        # Reuse exact fenced delivery reconciliation. A COMPLETE state may only
        # settle its own still-open contract; foreign/unproven state fails closed.
        return self.align(s)
    def prepare_pre_target(self,s:ReleaseState)->Outcome:
        marker=self.root/'Inbox/ha_publication_required.json'
        try:
            artifact=self._active_artifact(s)
            if artifact.parent.name!='processing':return Outcome.blocked('pre_target_artifact_not_processing')
            payload=self._pre_target_contract(s,artifact)
            self._ensure_contract(s,payload,marker)
        except Exception as exc:return Outcome.blocked(str(exc),'inspect exact pre-target publication ownership; do not delete foreign state')
        pub=_json(self.root/'Inbox/github_publication_state.json')
        if self._publisher_exact(pub,payload):return Outcome.green('github_pre_target_exact')
        elapsed=max(0.0,time.time()-float(s.phase_started_at_epoch or time.time()))
        if elapsed>=self.timeout:
            if pub.get('published') is False and self._identity_matches(pub,payload):
                return Outcome.blocked('github_pre_target_publication_failed','inspect exact publisher evidence; do not create a second release')
            return Outcome.blocked('github_pre_target_identity_timeout','inspect exact publisher evidence; do not install before GitHub target is exact')
        return Outcome.waiting('github_pre_target_pending','pre_target_publication_contract_ready')
    def align(self,s:ReleaseState)->Outcome:
        marker=self.root/'Inbox/ha_publication_required.json'
        try:
            artifact=self._active_artifact(s)
            existing=_json(marker)
            payload=self._pre_target_contract(s,artifact) if existing.get('source_stage')=='processing_pre_target' else self._contract(s,artifact)
            self._ensure_contract(s,payload,marker)
        except Exception as exc:return Outcome.blocked(str(exc),'inspect exact publication ownership; do not delete foreign state')
        pub=_json(self.root/'Inbox/github_publication_state.json')
        ha=_json(self.root/'Inbox/ha_runtime/current.json')
        pub_exact=self._publisher_exact(pub,payload)
        ha_exact=str(ha.get('version') or '')==s.to_version
        if pub_exact and ha_exact:
            try:
                # Controller-owned final settlement. Re-read identity immediately
                # before unlink so a foreign replacement can never be removed.
                current=_json(marker)
                if not self._identity_matches(current,payload):return Outcome.blocked('publication_contract_settlement_fence_conflict')
                marker.unlink()
                if marker.exists():return Outcome.blocked('publication_contract_settlement_readback_failed')
                self._archive_complete(s)
                # The publisher deliberately never owns contract removal. Once the
                # controller has settled the exact fenced contract, update the shared
                # publication state so observability reports current settlement truth
                # instead of leaving the legacy publisher-side False value behind.
                settled=dict(pub)
                settled.update({
                    'publication_contract_removed':True,
                    'publication_contract_settled':True,
                    'publication_contract_active':False,
                    'contract_settled_by':'release_controller',
                    'settled_release_id':s.release_id,
                    'settled_generation':s.generation,
                })
                _atomic(self.root/'Inbox/github_publication_state.json',settled)
            except Exception as exc:return Outcome.blocked(str(exc))
            return Outcome.green('github_target_exact','ha_runtime_current','publication_contract_settled','processed_archived')
        if pub_exact:
            # Home Assistant add-on updates are an explicit human action. Exact
            # GitHub publication therefore remains a durable normal wait, not a
            # delivery timeout or a second automatic actuator path.
            return Outcome.waiting('WAITING_MANUAL_HA_UPDATE','github_target_exact','ha_predecessor_runtime')
        elapsed=max(0.0,time.time()-float(s.phase_started_at_epoch or time.time()))
        if elapsed>=self.timeout:
            if pub.get('published') is False and self._identity_matches(pub,payload):
                return Outcome.blocked('github_publication_failed','inspect exact publisher evidence; do not create a second release')
            return Outcome.blocked('ha_delivery_identity_timeout','inspect exact publisher/runtime evidence; do not create a second release')
        return Outcome.waiting('github_publication_pending','publication_contract_ready')
