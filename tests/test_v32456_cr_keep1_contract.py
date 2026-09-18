import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for p in (str(APP), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_project_cr_active_executor_is_keep1_and_never_reports_delete():
    source = (ROOT / "tools/project_cr_local_executor.py").read_text(encoding="utf-8")
    assert "create_crash_recovery_backup(root,root/'Backups',retention=1)" in source
    assert "'retention':1" in source
    assert "'delete_performed':False" in source
    assert "retention_delete_performed" in source


def test_nas_cr_keep1_happens_only_after_new_set_validation():
    from nas_container_cr_service import NasContainerCrService

    source = inspect.getsource(NasContainerCrService.create)
    first_validation = source.index("if not self._validate_set(self.target, stem):")
    stage_keep1 = source.index("retention_tx = self._stage_keep1(stem)")
    marker_validation = source.index("require_retention_marker=True")
    commit_keep1 = source.index("retention = self._commit_keep1(retention_tx)")

    assert first_validation < stage_keep1 < marker_validation < commit_keep1
    assert "self._rollback_keep1(retention_tx)" in source


def test_nas_cr_retention_commit_is_quarantine_not_delete():
    from nas_container_cr_service import NasContainerCrService

    source = inspect.getsource(NasContainerCrService._commit_keep1)
    assert "Backups/CRRetentionQuarantine/NAS Container" in source
    assert "'delete_performed': False" in source
    assert ".unlink(" not in source
