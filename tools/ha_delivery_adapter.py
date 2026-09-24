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
        install_predecessor=active if active_version==s.from_version else self.root/f'App.__rollback_{s.from_version}'
        install_manifest=self._manifest_sha(install_predecessor/'MANIFEST.sha256')
        publication_version=s.from_version
        publication_manifest=install_manifest
        # Publication predecessor and local installation predecessor are separate
        # domains. After a partial publish + local rollback, GitHub/HA may be one
        # exact version ahead while the accepted local App correctly remains on
        # s.from_version. Only use the remote predecessor when both canonical
        # GitHub publication state and HA runtime prove the same exact identity.
        pub=_json(self.root/'Inbox/github_publication_state.json')
        ha=_json(self.root/'Inbox/ha_runtime/current.json')
        remote_version=str(pub.get('version') or '')
        remote_manifest=str(pub.get('target_manifest_sha256') or '')
        remote_head=str(pub.get('remote_head') or '')
        local_head=str(pub.get('local_head') or '')
        if (pub.get('published') is True and pub.get('target_exact') is True
                and remote_version and remote_manifest and remote_version!=s.to_version
                and str(ha.get('version') or '')==remote_version
                and remote_head and local_head and remote_head==local_head):
            publication_version=remote_version
            publication_manifest=remote_manifest
        return {'schema':'energie_ha_publication_contract_v2','status':'publication_required',
            'source_stage':'processing_pre_target','version':s.to_version,
            'repository':'https://github.com/kgnfn65498-droid/EnergieProject','branch':'main',
            'install_predecessor_version':s.from_version,
            'install_predecessor_manifest_sha256':install_manifest,
            'publication_predecessor_version':publication_version,
            'publication_predecessor_manifest_sha256':publication_manifest,
            # Legacy fields remain for the currently installed publisher and are
            # explicitly the publication-domain predecessor, never the install one.
            'expected_previous_version':publication_version,'expected_previous_manifest_sha256':publication_manifest,
            'predecessor_version':publication_version,'predecessor_manifest_sha256':publication_manifest,
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
    def _retire_proven_rolled_back_contract(self,s,existing,marker):
        # A pre-target contract can survive a release that was subsequently
        # rolled back.  Retire it only when independent filesystem evidence
        # proves that it belongs to a failed predecessor attempt from the same
        # active baseline.  Anything ambiguous remains fail-closed.
        old_version=str(existing.get('version') or '')
        old_zip=str(existing.get('processed_zip') or '')
        old_sha=str(existing.get('processed_zip_sha256') or '').lower()
        if not old_version or old_version==s.to_version:return False
        install_version=str(existing.get('install_predecessor_version') or existing.get('expected_previous_version') or '')
        if install_version!=s.from_version:return False
        if len(old_sha)!=64 or any(c not in '0123456789abcdef' for c in old_sha):return False
        if not old_zip.endswith('.zip') or Path(old_zip).name!=old_zip:return False
        active=self.root/'App/VERSIE.txt'
        if active.is_symlink() or not active.is_file() or active.read_text(encoding='utf-8').strip()!=s.from_version:return False
        journal=_json(self.root/'Inbox/atomic_app_swap_state.json')
        if str(journal.get('state') or '')!='ACCEPTED' or str(journal.get('to_version') or '')!=s.from_version:return False
        rolled_name=old_zip[:-4]+'.rolled_back.zip'
        rolled=self.root/'Inbox/failed/rolled_back'/rolled_name
        if rolled.is_symlink() or not rolled.is_file() or _sha(rolled)!=old_sha:return False
        pub=_json(self.root/'Inbox/github_publication_state.json')
        if pub.get('published') is not True or pub.get('target_exact') is not True:return False
        if not self._identity_matches(pub,existing):return False
        archive=self.root/'Inbox/failed/rolled_back'/(old_zip[:-4]+'.publication_contract.json')
        preserved=dict(existing);preserved['status']='retired_after_proven_rollback';preserved['retired_by_release_id']=s.release_id
        if archive.exists():
            if archive.is_symlink() or _json(archive)!=preserved:return False
        else:_atomic(archive,preserved)
        marker.unlink()
        return not marker.exists()
    def _ensure_contract(self,s,payload,marker):
        existing=_json(marker)
        if existing and any(existing.get(k)!=payload.get(k) for k in ('version','processed_zip','processed_zip_sha256')):
            if self._retire_proven_rolled_back_contract(s,existing,marker):existing={}
        if not existing:
            _atomic(marker,payload);return payload
        core=('source_stage','version','repository','branch','expected_previous_version','expected_previous_manifest_sha256','predecessor_version','predecessor_manifest_sha256','target_manifest_sha256','processed_zip','processed_zip_sha256')
        dual=('install_predecessor_version','install_predecessor_manifest_sha256','publication_predecessor_version','publication_predecessor_manifest_sha256')
        compare=core+tuple(k for k in dual if k in existing or k in payload)
        if any(existing.get(k)!=payload.get(k) for k in compare):raise RuntimeError('publication_contract_conflict')
        if str(existing.get('release_id') or '')!=s.release_id or str(existing.get('generation') or '')!=s.generation:
            raise RuntimeError('publication_contract_fence_conflict')
        return existing
    def _publisher_exact(self,pub,payload):
        return bool(pub.get('published') is True and pub.get('target_exact') is True and pub.get('remote_head') and self._identity_matches(pub,payload))
    def _completed_settlement_expected(self,s:ReleaseState):
        if str(getattr(s,'status',''))!='COMPLETE' or str(getattr(s,'phase',''))!='COMPLETE':
            raise RuntimeError('completed_reconcile_requires_complete_state')
        required={'github_target_exact','ha_runtime_current','publication_contract_settled','processed_archived'}
        if not required.issubset(set(getattr(s,'evidence',[]) or [])):
            raise RuntimeError('completed_reconcile_evidence_incomplete')
        active=self.root/'App/VERSIE.txt'
        if active.is_symlink() or not active.is_file() or active.read_text(encoding='utf-8').strip()!=s.to_version:
            raise RuntimeError('completed_reconcile_app_version_mismatch')
        ha=_json(self.root/'Inbox/ha_runtime/current.json')
        if str(ha.get('version') or '')!=s.to_version:
            raise RuntimeError('completed_reconcile_ha_version_mismatch')
        processed=self.root/'Inbox/processed'/s.artifact_name
        if processed.is_symlink() or not processed.is_file():
            raise RuntimeError('completed_reconcile_processed_missing_or_unsafe')
        if _sha(processed)!=s.artifact_sha256:
            raise RuntimeError('completed_reconcile_processed_hash_mismatch')
        pub_path=self.root/'Inbox/github_publication_state.json'
        pub=_json(pub_path)
        if not pub:
            raise RuntimeError('completed_reconcile_publication_missing_or_invalid')
        exact={
            'version':s.to_version,'release_id':s.release_id,'generation':s.generation,
            'processed_zip':s.artifact_name,'processed_zip_sha256':s.artifact_sha256,
            'target_manifest_sha256':self._target_manifest_sha(processed),
        }
        if pub.get('published') is not True or pub.get('target_exact') is not True:
            raise RuntimeError('completed_reconcile_publication_not_exact')
        if any(str(pub.get(k) or '')!=str(v) for k,v in exact.items()):
            raise RuntimeError('completed_reconcile_publication_identity_mismatch')
        remote=str(pub.get('remote_head') or '').strip();local=str(pub.get('local_head') or '').strip()
        if not remote or not local or remote!=local:
            raise RuntimeError('completed_reconcile_git_head_mismatch')
        marker=self.root/'Inbox/ha_publication_required.json'
        if marker.exists():
            current=_json(marker)
            if not current or not self._identity_matches(current,exact):
                raise RuntimeError('completed_reconcile_foreign_contract')
        return pub_path,pub,exact

    def _normalize_settlement_observability(self,s:ReleaseState)->Outcome:
        try:
            pub_path,pub,_=self._completed_settlement_expected(s)
            expected={
                'publication_contract_removed':True,
                'publication_contract_settled':True,
                'publication_contract_active':False,
                'contract_settled_by':'release_controller',
                'settled_release_id':s.release_id,
                'settled_generation':s.generation,
            }
            if all(pub.get(k)==v for k,v in expected.items()):
                return Outcome.green('completed_delivery_settled','settlement_observability_exact')
            updated=dict(pub);updated.update(expected);_atomic(pub_path,updated)
            readback=_json(pub_path)
            if any(readback.get(k)!=v for k,v in expected.items()):
                return Outcome.blocked('settlement_observability_readback_failed')
            if str(readback.get('release_id') or '')!=s.release_id or str(readback.get('generation') or '')!=s.generation:
                return Outcome.blocked('settlement_observability_identity_changed')
            return Outcome.green('completed_delivery_settled','settlement_observability_reconciled')
        except Exception as exc:
            return Outcome.blocked(str(exc),'preserve COMPLETE release; inspect exact completed-settlement evidence')

    def reconcile_completed_delivery(self,s:ReleaseState)->Outcome:
        marker=self.root/'Inbox/ha_publication_required.json'
        if marker.exists():
            # An open exact marker still uses the normal fenced settlement path.
            out=self.align(s)
            if out.status!='GREEN':return out
        pub=_json(self.root/'Inbox/github_publication_state.json')
        already_exact=bool(
            pub.get('publication_contract_removed') is True
            and pub.get('publication_contract_settled') is True
            and pub.get('publication_contract_active') is False
            and str(pub.get('contract_settled_by') or '')=='release_controller'
            and str(pub.get('settled_release_id') or '')==s.release_id
            and str(pub.get('settled_generation') or '')==s.generation
            and str(pub.get('version') or '')==s.to_version
            and str(pub.get('processed_zip') or '')==s.artifact_name
            and str(pub.get('processed_zip_sha256') or '')==s.artifact_sha256
        )
        if already_exact:
            return Outcome.green('completed_delivery_settled','settlement_observability_exact')
        # Marker absent is not enough proof. Missing/incomplete observability may
        # only be backfilled from exact COMPLETE + App + HA + Processed + GitHub
        # + manifest evidence.
        return self._normalize_settlement_observability(s)
    def prepare_pre_target(self,s:ReleaseState)->Outcome:
        marker=self.root/'Inbox/ha_publication_required.json'
        try:
            artifact=self._active_artifact(s)
            if artifact.parent.name!='processing':return Outcome.blocked('pre_target_artifact_not_processing')
            existing=_json(marker)
            pub=_json(self.root/'Inbox/github_publication_state.json')
            exact_expected={
                'version':s.to_version,'release_id':s.release_id,'generation':s.generation,
                'processed_zip':s.artifact_name,'processed_zip_sha256':s.artifact_sha256,
                'target_manifest_sha256':self._target_manifest_sha(artifact),
            }
            if existing and self._identity_matches(existing,exact_expected) and self._publisher_exact(pub,existing):
                return Outcome.green('github_pre_target_exact','target_publication_already_exact')
            payload=self._pre_target_contract(s,artifact)
            self._ensure_contract(s,payload,marker)
        except Exception as exc:return Outcome.blocked(str(exc),'inspect exact pre-target publication ownership; do not delete foreign state')
        pub=_json(self.root/'Inbox/github_publication_state.json')
        if self._publisher_exact(pub,payload):return Outcome.green('github_pre_target_exact')
        ha=_json(self.root/'Inbox/ha_runtime/current.json')
        install_version=str(payload.get('install_predecessor_version') or s.from_version)
        publication_version=str(payload.get('publication_predecessor_version') or payload.get('expected_previous_version') or '')
        publication_manifest=str(payload.get('publication_predecessor_manifest_sha256') or payload.get('expected_previous_manifest_sha256') or '')
        split_recovery=bool(publication_version and publication_version!=install_version)
        remote_predecessor_exact=bool(
            split_recovery and pub.get('published') is True and pub.get('target_exact') is True
            and str(pub.get('version') or '')==publication_version
            and str(pub.get('target_manifest_sha256') or '')==publication_manifest
            and str(ha.get('version') or '')==publication_version
            and str(pub.get('remote_head') or '') and str(pub.get('remote_head') or '')==str(pub.get('local_head') or '')
        )
        if remote_predecessor_exact:
            return Outcome.waiting('github_pre_target_pending','remote_predecessor_exact','split_state_recovery_active','pre_target_publication_contract_ready')
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
            pub=_json(self.root/'Inbox/github_publication_state.json')
            exact_existing=bool(
                existing.get('source_stage')=='processing_pre_target'
                and str(existing.get('version') or '')==s.to_version
                and str(existing.get('release_id') or '')==s.release_id
                and str(existing.get('generation') or '')==s.generation
                and str(existing.get('processed_zip') or '')==s.artifact_name
                and str(existing.get('processed_zip_sha256') or '')==s.artifact_sha256
                and self._publisher_exact(pub,existing)
            )
            if exact_existing:
                payload=existing
            else:
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
