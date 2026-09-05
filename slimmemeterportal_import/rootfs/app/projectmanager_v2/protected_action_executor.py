import hashlib
import json
import os
import shutil
from pathlib import Path


class ProtectedActionExecutor:
    """Local capability-bounded executor for already Peter-approved actions.

    Only production_deploy is executable in 32.4.4. It can only publish an
    exact, already fully verified release artifact to Inbox/incoming. No shell,
    arbitrary path, payment, purchase or direct production mutation is exposed.
    """

    def __init__(self, project_root, approved_actions, commands, decisions, *, audit=None):
        self.project_root = Path(project_root).resolve()
        self.approved_actions = approved_actions
        self.commands = commands
        self.decisions = decisions
        self.audit = audit
        self.staging_root = (self.project_root / 'Data/03_Systeem/Projectmanager/Staging').resolve()
        self.incoming_root = (self.project_root / 'Inbox/incoming').resolve()

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

    def run_once(self, *, max_items=5):
        results = []
        for action in self.approved_actions.open_items()[:max(0, int(max_items))]:
            if action.get('action') != 'production_deploy':
                # Unsupported protected capabilities are never executed silently.
                continue
            try:
                command = self.commands.get(action['command_id'])
                decision = self.decisions.get(action['decision_id'])
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
                self.approved_actions.complete(action['id'], result=result)
                self.commands.complete(command['id'], result=result)
                if self.audit is not None:
                    self.audit.write('protected_action.executed', actor='projectmanager', result='ok', details={
                        'action_id': action['id'], 'command_id': command['id'], 'action': action['action'],
                        'release_version': release_version, 'artifact_sha256': artifact_sha,
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
