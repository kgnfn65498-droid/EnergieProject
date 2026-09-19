from __future__ import annotations
import shutil,zipfile
from pathlib import Path
from release_controller import Outcome,ReleaseState

class AtomicReleaseAdapter:
    def __init__(self,root:Path,atomic_module,native_runtime,ha_delivery):
        self.root=Path(root);self.atomic=atomic_module;self.native=native_runtime;self.ha=ha_delivery
    def _paths(self,s):return self.atomic.SwapPaths.for_release(self.root,s.from_version,s.to_version)
    def _pm_version(self,path):
        p=Path(path)/'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt'
        v=p.read_text(encoding='utf-8').strip() if p.is_file() else ''
        if not v:raise RuntimeError('projectmanager_version_missing')
        return v
    def _target_pm_version(self,artifact):
        name='slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt'
        with zipfile.ZipFile(artifact) as z:v=z.read(name).decode().strip()
        if not v:raise RuntimeError('target_projectmanager_version_missing')
        return v
    def _journal(self,s):
        paths=self._paths(s);j=self.atomic.load_journal(paths)
        if j is None:return None
        j_from=str(j.get('from_version') or '')
        j_to=str(j.get('to_version') or '')
        j_sha=str(j.get('artifact_sha256') or '').lower()
        if j_from==s.from_version and j_to==s.to_version:
            if j_sha!=s.artifact_sha256.lower():raise RuntimeError('atomic_artifact_mismatch')
            return j
        # A single global atomic journal intentionally survives acceptance. For N+1,
        # accept it only as historical evidence when it is exactly the immediately
        # preceding ACCEPTED release and the physical active App still proves that
        # predecessor target. Every other mismatch remains fail-closed.
        if str(j.get('state') or '')=='ACCEPTED' and j_to==s.from_version:
            if len(j_sha)!=64 or any(c not in '0123456789abcdef' for c in j_sha):
                raise RuntimeError('atomic_previous_artifact_invalid')
            prior=self.atomic.SwapPaths.for_release(self.root,j_from,j_to)
            if str(j.get('candidate_path') or '')!=prior.candidate.name:
                raise RuntimeError('atomic_previous_candidate_path_mismatch')
            if str(j.get('rollback_path') or '')!=prior.rollback.name:
                raise RuntimeError('atomic_previous_rollback_path_mismatch')
            proven=self.atomic.reconcile_state(prior)
            if str(proven.get('state') or '')!='ACCEPTED':
                raise RuntimeError('atomic_previous_acceptance_unproven')
            return None
        if j_from!=s.from_version:raise RuntimeError('atomic_from_version_mismatch')
        if j_to!=s.to_version:raise RuntimeError('atomic_to_version_mismatch')
        raise RuntimeError('atomic_artifact_mismatch')
    def _cleanup_unpromoted_candidate(self,s):
        paths=self._paths(s)
        active=(paths.app/'VERSIE.txt').read_text(encoding='utf-8').strip() if (paths.app/'VERSIE.txt').is_file() else ''
        if active!=s.from_version:raise RuntimeError('candidate_cleanup_source_not_restored')
        if paths.rollback.exists():raise RuntimeError('candidate_cleanup_rollback_still_present')
        j=self._journal(s)
        atom=str((j or {}).get('state') or '')
        if atom not in {'','PREPARED','ROLLED_BACK'}:
            raise RuntimeError('candidate_cleanup_atomic_state_invalid:'+atom)
        if not paths.candidate.exists():return []
        if paths.candidate.is_symlink() or not paths.candidate.is_dir():
            raise RuntimeError('candidate_cleanup_target_unsafe')
        shutil.rmtree(paths.candidate)
        if paths.candidate.exists():raise RuntimeError('candidate_cleanup_readback_failed')
        return ['unpromoted_candidate_removed']
    def _settle_pre_activation_rollback(self,s,reason):
        paths=self._paths(s);j=self._journal(s);atom=str((j or {}).get('state') or '')
        if atom not in {'','PREPARED','ROLLED_BACK'}:
            raise RuntimeError('pre_activation_rollback_state_invalid:'+atom)
        evidence=self._cleanup_unpromoted_candidate(s)
        if atom=='PREPARED':
            self.atomic.write_journal_atomic(paths,state='ROLLED_BACK',artifact_sha256=s.artifact_sha256,
                error='pre-activation rollback: '+str(reason))
            evidence.append('atomic_prepared_marked_rolled_back')
        return evidence
    def _blocked_pre_activation_source_unchanged(self,s):
        if str(getattr(s,'phase',''))!='INSTALLING' or str(getattr(s,'status',''))!='BLOCKED':return None
        if str(getattr(s,'blocker',''))!='rollback_unproven':return None
        paths=self._paths(s)
        active=(paths.app/'VERSIE.txt').read_text(encoding='utf-8').strip() if (paths.app/'VERSIE.txt').is_file() else ''
        if active!=s.from_version:return None
        if paths.candidate.exists() or paths.rollback.exists():return None
        raw=self.atomic.load_journal(paths)
        if not isinstance(raw,dict) or str(raw.get('state') or '')!='ACCEPTED':return None
        if str(raw.get('to_version') or '')!=s.from_version:return None
        # _journal performs the strict previous-release identity, path, SHA and
        # physical ACCEPTED reconciliation. Only its historical-None result is
        # valid evidence that no current-release atomic mutation ever started.
        if self._journal(s) is not None:return None
        return ['source_app_restored','previous_atomic_acceptance_preserved']
    def install(self,s):
        recovery=self._blocked_pre_activation_source_unchanged(s)
        if recovery is not None:return Outcome.rolled_back('pre_activation_source_unchanged',*recovery)
        paths=self._paths(s);artifact=self.root/'Inbox/processing'/s.artifact_name
        try:
            j=self._journal(s)
            if j is not None:
                reconciled=self.atomic.reconcile_state(paths);atom=str(reconciled.get('state') or '')
                if atom=='ROLLED_BACK':
                    ev=self._settle_pre_activation_rollback(s,'reconciled rolled back')
                    return Outcome.rolled_back('atomic_reconciled_rolled_back','source_app_restored',*ev)
                if atom in {'NEW_ACTIVE','LIVE_ACCEPTANCE','ACCEPTED'}:return Outcome.green('atomic_resume:'+atom)
                if atom!='PREPARED':return Outcome.blocked('atomic_unexpected_state:'+atom)
                target_pm=self._target_pm_version(artifact)
                result=self.atomic.perform_swap(paths,artifact_sha256=s.artifact_sha256,expected_target_pm_version=target_pm)
                return Outcome.green('atomic_resumed:'+str(result.get('state') or ''))
            source_pm=self._pm_version(self.root/'App');target_pm=self._target_pm_version(artifact)
            self.atomic.verify_release_artifact(artifact,s.artifact_sha256)
            self.atomic.verify_source_baseline(paths,expected_pm_version=source_pm)
            self.atomic.materialize_candidate(paths,artifact,expected_pm_version=target_pm)
            self.atomic.verify_same_filesystem(paths);self.atomic.probe_sibling_rename(paths)
            result=self.atomic.perform_swap(paths,artifact_sha256=s.artifact_sha256,expected_target_pm_version=target_pm)
            return Outcome.green('atomic_install:'+str(result.get('state') or ''))
        except Exception as exc:
            try:j=self._journal(s) or {}
            except Exception:j={}
            if str(j.get('state') or '')=='ROLLED_BACK':
                ev=self._settle_pre_activation_rollback(s,'install rolled back')
                return Outcome.rolled_back('atomic_install_rolled_back','source_app_restored',*ev)
            return Outcome.blocked('atomic_install_failed:'+type(exc).__name__,rollback=True)
    def runtime_align(self,s):return self.native.align(s)
    def verify_live(self,s):
        try:
            paths=self._paths(s);j=self.atomic.reconcile_state(paths)
            # ACCEPTED is valid crash-recovery evidence when atomic acceptance
            # committed just before the controller state save. Re-running
            # atomic_accept is idempotent and will settle the central phase.
            if str(j.get('state') or '') not in {'NEW_ACTIVE','LIVE_ACCEPTANCE','ACCEPTED'}:
                return Outcome.blocked('atomic_not_live_acceptance',rollback=True)
            if (self.root/'App/VERSIE.txt').read_text().strip()!=s.to_version:return Outcome.blocked('active_version_mismatch',rollback=True)
            if self.native.guard.probe(self.root).get('ready') is not True:return Outcome.blocked('native_mcp_not_current',rollback=True)
            return Outcome.green('active_version_current','native_mcp_current')
        except Exception as exc:return Outcome.blocked('live_verify_failed:'+type(exc).__name__,rollback=True)
    def atomic_accept(self,s):
        try:
            paths=self._paths(s);j=self._journal(s) or {};atom=str(j.get('state') or '')
            if atom=='ACCEPTED':return Outcome.green('atomic_already_accepted')
            if atom!='LIVE_ACCEPTANCE':return Outcome.blocked('atomic_accept_state_invalid:'+atom,rollback=True)
            target_pm=self._pm_version(self.root/'App')
            result=self.atomic.finalize_acceptance(paths,expected_target_pm_version=target_pm)
            return Outcome.green('atomic_accept:'+str(result.get('state') or ''))
        except Exception as exc:return Outcome.blocked('atomic_accept_failed:'+type(exc).__name__,rollback=True)
    def delivery(self,s):return self.ha.align(s)
    def rollback(self,s,reason):
        try:
            paths=self._paths(s);j=self._journal(s) or {};atom=str(j.get('state') or '')
            if atom=='ROLLED_BACK':
                ev=self._settle_pre_activation_rollback(s,reason)
                return Outcome.rolled_back('atomic_already_rolled_back','source_app_restored',*ev)
            if atom=='OLD_RENAMED':
                r=self.atomic.reconcile_state(paths)
                ev=self._settle_pre_activation_rollback(s,reason)
                return Outcome.rolled_back('atomic_reconciled:'+str(r.get('state') or ''),'source_app_restored',*ev)
            if atom in {'NEW_ACTIVE','LIVE_ACCEPTANCE'}:
                r=self.atomic.rollback_after_activation_failure(paths,reason=reason)
                return Outcome.rolled_back('atomic_rollback:'+str(r.get('state') or ''),'source_app_restored')
            if atom in {'','PREPARED'}:
                ev=self._settle_pre_activation_rollback(s,reason)
                return Outcome.rolled_back('atomic_source_still_active','source_app_restored',*ev)
            return Outcome.blocked('atomic_rollback_state_invalid:'+atom,'manual filesystem evidence required')
        except Exception as exc:return Outcome.blocked('atomic_rollback_failed:'+type(exc).__name__,'manual filesystem evidence required')
