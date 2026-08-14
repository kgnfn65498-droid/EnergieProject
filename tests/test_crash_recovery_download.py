import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_recovery_path_mapping_stays_inside_backup_root(tmp_path):
    m = load_main("download_path_mapping")
    m.PROJECT_BACKUP_ROOT = tmp_path / "Backups"

    expected = (m.PROJECT_BACKUP_ROOT / "RestoreStaging" / "run-1").resolve()
    assert m._recovery_path_to_project_backup("/recovery/RestoreStaging/run-1") == expected
    assert m._recovery_path_to_project_backup("/tmp/not-recovery") is None
    assert m._recovery_path_to_project_backup("/recovery/../outside") is None
    assert m._recovery_path_to_project_backup("/recovery") == m.PROJECT_BACKUP_ROOT.resolve()


def test_validated_download_path_requires_export_root_and_matching_sha(tmp_path):
    m = load_main("download_validate")
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"
    m.CRASH_RECOVERY_EXPORT_ROOT.mkdir(parents=True)
    export_path = m.CRASH_RECOVERY_EXPORT_ROOT / "EnergieProject_Complete_Crash_Recovery_test.zip"
    export_path.write_bytes(b"abc")
    sha = m.sha256_file(export_path)

    state = {
        "status": "ready_for_download",
        "download_status": "ready",
        "export_path": str(export_path),
        "export_sha256": sha,
    }
    assert m._validated_export_download_path(state) == export_path.resolve()

    bad_sha = dict(state, export_sha256="0" * 64)
    try:
        m._validated_export_download_path(bad_sha)
    except RuntimeError as exc:
        assert "SHA" in str(exc)
    else:
        raise AssertionError("verkeerde SHA werd geaccepteerd")

    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"abc")
    outside_state = dict(state, export_path=str(outside), export_sha256=m.sha256_file(outside))
    try:
        m._validated_export_download_path(outside_state)
    except RuntimeError as exc:
        assert "export" in str(exc).lower()
    else:
        raise AssertionError("download buiten exportroot werd geaccepteerd")


def test_cleanup_only_removes_exact_run_artifacts(tmp_path):
    m = load_main("download_cleanup")
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"
    m.PROJECT_BACKUP_ROOT = tmp_path / "Backups"
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    export_path = m.CRASH_RECOVERY_EXPORT_ROOT / "EnergieProject_Complete_Crash_Recovery_test.zip"
    export_path.parent.mkdir(parents=True)
    export_path.write_bytes(b"export")

    backup_name = "Energie_Complete_Backup_2026_08_test.zip"
    backup_path = m.PROJECT_BACKUP_ROOT / backup_name
    backup_path.parent.mkdir(parents=True)
    backup_path.write_bytes(b"source")

    manifests = m.PROJECT_BACKUP_ROOT / "Manifests"
    manifests.mkdir(parents=True)
    run_manifest = manifests / "Energie_Complete_Backup_2026_08_test_manifest.json"
    run_manifest.write_text("{}", encoding="utf-8")
    keep_manifest = manifests / "historische_maand_manifest.json"
    keep_manifest.write_text("{}", encoding="utf-8")

    staging = m.PROJECT_BACKUP_ROOT / "RestoreStaging" / "run-1"
    staging.mkdir(parents=True)
    (staging / "restored.txt").write_text("ok", encoding="utf-8")

    month_backup = m.PROJECT_BACKUP_ROOT / "EnergieProject_maandbackup_2026_07.zip"
    month_backup.write_bytes(b"month")
    full_recovery = m.PROJECT_BACKUP_ROOT / "FULL_RECOVERY_old.tar.gz"
    full_recovery.write_bytes(b"old")

    state = {
        "status": "ready_for_download",
        "download_status": "downloaded",
        "export_path": str(export_path),
        "backup_name": backup_name,
        "restore_staging_path": "/recovery/RestoreStaging/run-1",
    }
    result = m._cleanup_completed_export(state)

    assert result["status"] == "ok"
    assert not export_path.exists()
    assert not backup_path.exists()
    assert not run_manifest.exists()
    assert not staging.exists()

    assert month_backup.exists()
    assert full_recovery.exists()
    assert keep_manifest.exists()
    assert m.PROJECT_BACKUP_ROOT.exists()
    assert manifests.exists()


def test_cleanup_never_deletes_month_backup_as_source(tmp_path):
    m = load_main("download_cleanup_month_guard")
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"
    m.PROJECT_BACKUP_ROOT = tmp_path / "Backups"

    export_path = m.CRASH_RECOVERY_EXPORT_ROOT / "export.zip"
    export_path.parent.mkdir(parents=True)
    export_path.write_bytes(b"export")
    month_name = "EnergieProject_maandbackup_2026_07.zip"
    month_path = m.PROJECT_BACKUP_ROOT / month_name
    month_path.parent.mkdir(parents=True)
    month_path.write_bytes(b"month")

    result = m._cleanup_completed_export({
        "download_status": "downloaded",
        "export_path": str(export_path),
        "backup_name": month_name,
        "restore_staging_path": "",
    })

    assert month_path.exists()
    assert not export_path.exists()
    assert result["status"] in {"ok", "warning"}


class RecordingWriter:
    def __init__(self, fail=False):
        self.data = bytearray()
        self.fail = fail
        self.flushed = False

    def write(self, data):
        if self.fail:
            raise BrokenPipeError("client closed")
        self.data.extend(data)
        return len(data)

    def flush(self):
        self.flushed = True


def _download_fixture(m, tmp_path):
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"
    m.PROJECT_BACKUP_ROOT = tmp_path / "Backups"
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    export_path = m.CRASH_RECOVERY_EXPORT_ROOT / "EnergieProject_Complete_Crash_Recovery_test.zip"
    export_path.parent.mkdir(parents=True)
    payload = b"0123456789" * 100
    export_path.write_bytes(payload)

    backup_name = "Energie_Complete_Backup_2026_08_test.zip"
    backup_path = m.PROJECT_BACKUP_ROOT / backup_name
    backup_path.parent.mkdir(parents=True)
    backup_path.write_bytes(b"source")

    staging = m.PROJECT_BACKUP_ROOT / "RestoreStaging" / "run-1"
    staging.mkdir(parents=True)
    (staging / "x").write_text("x", encoding="utf-8")

    state = {
        "status": "ready_for_download",
        "download_status": "ready",
        "cleanup_status": "pending",
        "export_path": str(export_path),
        "export_name": export_path.name,
        "export_sha256": m.sha256_file(export_path),
        "backup_name": backup_name,
        "restore_staging_path": "/recovery/RestoreStaging/run-1",
    }
    m._save_complete_recovery_state(state)
    return state, payload, export_path, backup_path, staging


def test_successful_stream_marks_downloaded_and_cleans_run(tmp_path):
    m = load_main("download_stream_success")
    state, payload, export_path, backup_path, staging = _download_fixture(m, tmp_path)
    writer = RecordingWriter()

    result = m._stream_complete_recovery_download(writer)

    assert bytes(writer.data) == payload
    assert writer.flushed is True
    assert result["status"] == "downloaded"
    assert result["download_status"] == "downloaded"
    assert result["cleanup_status"] == "ok"
    assert not export_path.exists()
    assert not backup_path.exists()
    assert not staging.exists()


def test_broken_stream_keeps_all_run_artifacts_for_retry(tmp_path):
    m = load_main("download_stream_broken")
    state, payload, export_path, backup_path, staging = _download_fixture(m, tmp_path)
    writer = RecordingWriter(fail=True)

    result = m._stream_complete_recovery_download(writer)

    assert result["status"] == "retry_available"
    assert result["download_status"] == "retry_available"
    assert result["cleanup_status"] == "pending"
    assert export_path.exists()
    assert backup_path.exists()
    assert staging.exists()


def test_download_route_is_real_get_endpoint():
    source = MAIN.read_text(encoding="utf-8")
    assert 'endswith("/api/crash-recovery/download")' in source
    assert 'Content-Type", "application/zip"' in source
    assert "Content-Disposition" in source


def test_crash_recovery_export_filename_is_readable_and_filesystem_safe():
    m = load_main("download_readable_filename")
    when = m.datetime(2026, 8, 14, 10, 30, tzinfo=m.TZ)
    name = m._crash_recovery_export_filename(when)
    assert name == "2026-08-14 10.30 CrashRecovery EnergieProject.zip"
    assert ":" not in name
