import hashlib
import json
import os
import shutil
import time
from pathlib import Path


class ProtectedActionExecutor:
    """Local capability-bounded executor for already Peter-approved actions.

    Production deploy can publish only an exact verified artifact to Incoming.
    Native MCP reload can only queue and later verify the fixed protected restart
    of energie-filesystem-mcp. No generic shell, container name or Docker command
    is exposed by this executor.
    """

    def __init__(self, project_root, approved_actions, commands, decisions, *, audit=None):
        self.project_root = Path(project_root).resolve()
        self.approved_actions = approved_actions
        self.commands = commands
        self.decisions = decisions
        self.audit = audit
        self.staging_root = (self.project_root / 'Data/03_Systeem/Projectmanager/Staging').resolve()
        self.incoming_root = (self.project_root / 'Inbox/incoming').resolve()
        self.native_mcp_runtime_root = (self.project_root / 'Inbox/native_mcp_runtime').resolve()
        self.control_plane_request_root = (self.project_root / 'Inbox/control_plane/requests').resolve()
        self.control_plane_result_root = (self.project_root / 'Inbox/control_plane/results').resolve()

    @staticmethod
    def _sha256(path: Path):
        h = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _inside(path: Path, root: Path):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _verify_release(self, command, decision):
        if decision.get('status') != 'APPROVED' or decision.get('approved_by') != 'Peter':
            raise RuntimeError('Peter approval missing')
        artifact_raw = str(command.get('artifact_path') or '').strip()
        report_raw = str(command.get('verification_report') or '').strip()
        expected_sha = str(command.get('artifact_sha256') or '').strip().lower()
        release_version = str(command.get('release_version') or '').strip()
        if not all((artifact_raw, report_raw, expected_sha, release_version)):
            raise RuntimeError('verified release coordinates missing from approved command')

        artifact = Path(artifact_raw)
        report_path = Path(report_raw)
        if not artifact.is_absolute():
            artifact = self.project_root / artifact
        if not report_path.is_absolute():
            report_path = self.project_root / report_path
        artifact = artifact.resolve()
        report_path = report_path.resolve()
        if not self._inside(artifact, self.staging_root) or not self._inside(report_path, self.staging_root):
            raise RuntimeError('artifact/report outside approved staging root')
        if not artifact.is_file() or artifact.suffix.lower() != '.zip':
            raise RuntimeError('release artifact missing or not zip')
        if not report_path.is_file():
            raise RuntimeError('verification report missing')
        actual_sha = self._sha256(artifact)
        if actual_sha != expected_sha:
            raise RuntimeError('artifact sha256 mismatch')

        report = json.loads(report_path.read_text(encoding='utf-8'))
        if not isinstance(report, dict) or report.get('overall') != 'GREEN':
            raise RuntimeError('verification report not GREEN')
        if report.get('production_modified') is not False:
            raise RuntimeError('verification report does not prove isolated staging')
        if str(report.get('release') or '') != release_version:
            raise RuntimeError('verification report release mismatch')
        report_artifact = report.get('artifact') or {}
        if isinstance(report_artifact, dict):
            report_sha = str(report_artifact.get('sha256') or '')
        else:
            report_sha = str(report.get('sha256') or '')
        if report_sha and report_sha != expected_sha:
            raise RuntimeError('verification report artifact hash mismatch')
        return artifact, expected_sha, release_version, report_path

    def _publish_once(self, artifact: Path):
        self.incoming_root.mkdir(parents=True, exist_ok=True)
        target = self.incoming_root / artifact.name
        if target.exists():
            if self._sha256(target) == self._sha256(artifact):
                return target, False
            raise RuntimeError('incoming target exists with different content')
        temp = self.incoming_root / f'.{artifact.name}.pmv2.tmp'
        if temp.exists():
            temp.unlink()
        try:
            with artifact.open('rb') as src, temp.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            os.replace(temp, target)
            try:
                dir_fd = os.open(str(self.incoming_root), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
            return target, True
        except Exception:
            try:
                temp.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _atomic_json(path: Path, payload: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise RuntimeError(f'onveilig request/result pad: {path}')
        temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    @staticmethod
    def _read_json_object(path: Path):
        if not path.is_file() or path.is_symlink():
            return None
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None

    def _queue_native_mcp_reload(self, action, command, decision):
        if decision.get('status') != 'APPROVED' or decision.get('approved_by') != 'Peter' or decision.get('kind') != 'PRODUCTION_RESTART':
            raise RuntimeError('Peter PRODUCTION_RESTART approval missing')

        request_id = hashlib.sha256(str(action['id']).encode('utf-8')).hexdigest()[:32]
        guard_path = self.native_mcp_runtime_root / 'runtime_guard.json'
        guard = self._read_json_object(guard_path)
        if not guard:
            raise RuntimeError('native MCP runtime guard ontbreekt')
        expected = str(guard.get('expected_fingerprint') or '').lower()
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise RuntimeError('native MCP expected fingerprint ongeldig')

        # Runtime truth wins.  A manual/bootstrap restart may already have made
        # the exact source/runtime fingerprint GREEN before PM reaches this
        # approved action.  Never perform a second unnecessary restart.
        if (
            guard.get('status') == 'GREEN'
            and guard.get('ready') is True
            and guard.get('reload_required') is False
            and str(guard.get('runtime_fingerprint') or '').lower() == expected
        ):
            return {
                'ok': True, 'executed': False, 'production_changed': False,
                'restart_performed': False, 'already_runtime_green': True,
                'runtime_green': True, 'request_id': request_id,
                'expected_fingerprint': expected, 'runtime_fingerprint': expected,
                'evidence_ref': str(guard_path),
            }

        result_path = self.control_plane_result_root / 'native_mcp_reload.json'
        proof = self._read_json_object(result_path)
        if proof and proof.get('request_id') == request_id:
            if not (
                proof.get('schema') == 'energie_native_mcp_reload_result_v1'
                and proof.get('status') == 'GREEN' and proof.get('ok') is True
                and proof.get('container') == 'energie-filesystem-mcp'
                and str(proof.get('expected_fingerprint') or '').lower() == expected
                and str(proof.get('runtime_fingerprint') or '').lower() == expected
                and proof.get('restart_performed') is True
            ):
                raise RuntimeError('control-plane native MCP result niet volledig GREEN')
            return {
                'ok': True, 'executed': True, 'production_changed': True,
                'restart_performed': True, 'runtime_green': True,
                'request_id': request_id, 'expected_fingerprint': expected,
                'result_path': str(result_path),
            }

        if guard.get('status') != 'RELOAD_REQUIRED' or guard.get('reload_required') is not True:
            raise RuntimeError('native MCP reload is niet aantoonbaar vereist')
        legacy_pending = self._read_json_object(self.native_mcp_runtime_root / 'reload_request.json')
        if legacy_pending is not None:
            raise RuntimeError('legacy native MCP pending request bestaat; eerst reconciliëren')
        payload = {
            'schema': 'energie_control_plane_request_v1',
            'request_id': request_id,
            'action': 'native_mcp_reload',
            'approved_by': 'Peter',
            'decision_id': decision['id'],
            'expected_fingerprint': expected,
        }
        target = self.control_plane_request_root / 'native_mcp_reload.json'
        pending = self._read_json_object(target)
        if pending is not None and pending != payload:
            raise RuntimeError('control-plane native MCP pending request conflicteert')
        if pending is None:
            self._atomic_json(target, payload)
        return {
            'ok': True, 'executed': False, 'awaiting_executor': True,
            'production_changed': False, 'restart_queued': True,
            'request_id': request_id, 'expected_fingerprint': expected,
            'request_path': str(target),
        }

    def _queue_watcher_recreate(self, action, command, decision):
        if decision.get('status') != 'APPROVED' or decision.get('approved_by') != 'Peter' or decision.get('kind') != 'PRODUCTION_RESTART':
            raise RuntimeError('Peter PRODUCTION_RESTART approval missing')
        request_id = hashlib.sha256(str(action['id']).encode('utf-8')).hexdigest()[:32]
        marker = self.project_root / 'Inbox/watcher_container_contract.json'
        proof = self._read_json_object(marker)
        if proof and proof.get('status') == 'GREEN' and proof.get('ready') is True and int(proof.get('contract_version') or 0) == 3:
            return {
                'ok': True, 'executed': False, 'production_changed': False,
                'restart_performed': False, 'already_runtime_green': True,
                'watcher_contract_green': True, 'contract_version': 3,
                'request_id': request_id, 'evidence_ref': str(marker),
            }

        result_path = self.control_plane_result_root / 'watcher_recreate.json'
        legacy_result_path = self.project_root / 'Inbox/control_plane/watcher_recreate_result.json'
        result = self._read_json_object(result_path) or self._read_json_object(legacy_result_path)
        if result is not None and not result_path.is_file():
            result_path = legacy_result_path
        if result and result.get('request_id') == request_id:
            if not (result.get('schema') == 'energie_control_plane_result_v1' and result.get('status') == 'GREEN' and result.get('ok') is True and int(result.get('contract_version') or 0) == 3):
                raise RuntimeError('control-plane watcher result niet volledig GREEN')
            return {
                'ok': True, 'executed': True, 'production_changed': True,
                'restart_performed': True, 'watcher_contract_green': True,
                'contract_version': 3, 'request_id': request_id,
                'result_path': str(result_path),
            }

        version_path = self.project_root / 'App/VERSIE.txt'
        release_version = version_path.read_text(encoding='utf-8').strip()
        payload = {
            'schema': 'energie_watcher_recreate_request_v1',
            'request_id': request_id,
            'operation': 'recreate_exact_energie_release_watcher',
            'release_version': release_version,
            'container': 'energie-release-watcher',
            'contract_version': 3,
            'confirmation_required': f'RECREATE WATCHER {release_version}',
        }
        target = self.project_root / 'Inbox/watcher_recreate_request.json'
        pending = self._read_json_object(target)
        if pending is not None and pending.get('request_id') != request_id:
            # A stale request may exist from a previous release.  It is safe to
            # replace only because the current approved action and decision are
            # exact and the dedicated control-plane revalidates both.
            pass
        self._atomic_json(target, payload)
        return {
            'ok': True, 'executed': False, 'awaiting_executor': True,
            'production_changed': False, 'restart_queued': True,
            'request_id': request_id, 'request_path': str(target),
        }

    def run_once(self, *, max_items=5):
        results = []
        for action in self.approved_actions.open_items()[:max(0, int(max_items))]:
            if action.get('action') not in {'production_deploy', 'native_mcp_reload', 'watcher_recreate'}:
                continue
            try:
                command = self.commands.get(action['command_id'])
                decision = self.decisions.get(action['decision_id'])
                if action.get('action') == 'production_deploy':
                    artifact, artifact_sha, release_version, report_path = self._verify_release(command, decision)
                    target, published = self._publish_once(artifact)
                    result = {
                        'ok': True,
                        'executed': True,
                        'production_changed': False,
                        'release_published_to_incoming': True,
                        'published_now': published,
                        'release_version': release_version,
                        'artifact_sha256': artifact_sha,
                        'verification_report': str(report_path),
                        'incoming_path': str(target),
                    }
                elif action.get('action') == 'native_mcp_reload':
                    result = self._queue_native_mcp_reload(action, command, decision)
                    if result.get('awaiting_executor') is True:
                        if self.audit is not None:
                            self.audit.write('protected_action.queued', actor='projectmanager', result='pending', details={
                                'action_id': action['id'], 'command_id': command['id'], 'action': action['action'],
                                'request_id': result.get('request_id'),
                            })
                        results.append(result)
                        continue
                else:
                    result = self._queue_watcher_recreate(action, command, decision)
                    if result.get('awaiting_executor') is True:
                        if self.audit is not None:
                            self.audit.write('protected_action.queued', actor='projectmanager', result='pending', details={
                                'action_id': action['id'], 'command_id': command['id'], 'action': action['action'],
                                'request_id': result.get('request_id'),
                            })
                        results.append(result)
                        continue
                self.approved_actions.complete(action['id'], result=result)
                self.commands.complete(command['id'], result=result)
                if self.audit is not None:
                    self.audit.write('protected_action.executed', actor='projectmanager', result='ok', details={
                        'action_id': action['id'], 'command_id': command['id'], 'action': action['action'],
                        'result': result,
                    })
                results.append(result)
            except Exception as exc:
                if self.audit is not None:
                    self.audit.write('protected_action.deferred', actor='projectmanager', result='blocked', details={
                        'action_id': action.get('id'), 'command_id': action.get('command_id'),
                        'reason': f'{type(exc).__name__}: {exc}',
                    })
                results.append({
                    'ok': False,
                    'executed': False,
                    'action_id': action.get('id'),
                    'reason': f'{type(exc).__name__}: {exc}',
                })
        return results

