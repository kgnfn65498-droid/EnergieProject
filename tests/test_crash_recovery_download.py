import importlib.util
import json
import pathlib
import subprocess
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


def test_cleanup_request_is_strictly_derived_from_run_state(tmp_path):
    m = load_main("download_cleanup_request")
    m.NAS_RELEASE_ROOT = tmp_path / "Inbox"
    m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_request.json"
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_result.json"

    backup_name = "Energie_Complete_Backup_2026_08_test.zip"
    state = {
        "download_status": "downloaded",
        "backup_name": backup_name,
        "restore_staging_path": "/recovery/RestoreStaging/run-1",
        "export_sha256": "a" * 64,
    }
    request = m._queue_crash_recovery_cleanup(state)

    assert request["schema"] == 1
    assert request["backup_name"] == backup_name
    assert request["manifest_name"] == "Energie_Complete_Backup_2026_08_test_manifest.json"
    assert request["restore_staging_path"] == "/recovery/RestoreStaging/run-1"
    persisted = json.loads(m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.read_text(encoding="utf-8"))
    assert persisted == request


def test_cleanup_request_refuses_non_complete_backup(tmp_path):
    m = load_main("download_cleanup_request_guard")
    m.NAS_RELEASE_ROOT = tmp_path / "Inbox"
    m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_request.json"
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_result.json"

    state = {
        "download_status": "downloaded",
        "backup_name": "EnergieProject_maandbackup_2026_07.zip",
        "restore_staging_path": "/recovery/RestoreStaging/run-1",
    }
    try:
        m._queue_crash_recovery_cleanup(state)
    except RuntimeError as exc:
        assert "backup" in str(exc).lower()
    else:
        raise AssertionError("maandbackup werd als Crash Recovery cleanup geaccepteerd")
    assert not m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.exists()


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
    m.NAS_RELEASE_ROOT = tmp_path / "NAS" / "Inbox"
    m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_request.json"
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_result.json"

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


def test_successful_stream_marks_downloaded_and_queues_watcher_cleanup(tmp_path):
    m = load_main("download_stream_success")
    state, payload, export_path, backup_path, staging = _download_fixture(m, tmp_path)
    writer = RecordingWriter()

    result = m._stream_complete_recovery_download(writer)

    assert bytes(writer.data) == payload
    assert writer.flushed is True
    assert result["status"] == "downloaded"
    assert result["download_status"] == "downloaded"
    assert result["cleanup_status"] == "pending_watcher"
    assert not export_path.exists()
    assert backup_path.exists()
    assert staging.exists()
    request = json.loads(m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.read_text(encoding="utf-8"))
    assert request["backup_name"] == state["backup_name"]
    assert request["manifest_name"] == f"{pathlib.Path(state['backup_name']).stem}_manifest.json"
    assert request["restore_staging_path"] == state["restore_staging_path"]
    assert result["cleanup_request_id"] == request["request_id"]


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
    assert not m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.exists()


def test_state_reconciles_watcher_result_to_cleanup_ok(tmp_path):
    m = load_main("download_cleanup_reconcile")
    state, payload, export_path, backup_path, staging = _download_fixture(m, tmp_path)
    writer = RecordingWriter()
    streamed = m._stream_complete_recovery_download(writer)
    request = json.loads(m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.read_text(encoding="utf-8"))

    result_payload = {
        "schema": 1,
        "request_id": request["request_id"],
        "status": "ok",
        "removed": ["backup", "manifest", "restore_staging"],
        "already_absent": [],
        "warnings": [],
    }
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH.write_text(json.dumps(result_payload), encoding="utf-8")

    reconciled = m._complete_recovery_state()
    assert reconciled["status"] == "downloaded"
    assert reconciled["cleanup_status"] == "ok"
    assert reconciled["cleanup_removed"] == result_payload["removed"]
    assert reconciled["cleanup_warnings"] == []


def test_v32031_downloaded_warning_is_requeued_without_new_backup(tmp_path):
    m = load_main("download_cleanup_migrate_warning")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.NAS_RELEASE_ROOT = tmp_path / "NAS" / "Inbox"
    m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_request.json"
    m.CRASH_RECOVERY_CLEANUP_RESULT_PATH = m.NAS_RELEASE_ROOT / "crash_recovery_cleanup_result.json"

    old = {
        "status": "downloaded",
        "version": "32.0.31",
        "download_status": "downloaded",
        "cleanup_status": "warning",
        "backup_name": "Energie_Complete_Backup_2026_08_old.zip",
        "restore_staging_path": "/recovery/RestoreStaging/old-run",
        "export_sha256": "b" * 64,
        "cleanup_warnings": ["RestoreStaging cleanup mislukt: permission denied"],
    }
    m._save_complete_recovery_state(old)

    migrated = m._complete_recovery_state()
    assert migrated["status"] == "downloaded"
    assert migrated["cleanup_status"] == "pending_watcher"
    assert migrated["cleanup_migrated_from"] == "32.0.31"
    request = json.loads(m.CRASH_RECOVERY_CLEANUP_REQUEST_PATH.read_text(encoding="utf-8"))
    assert request["backup_name"] == old["backup_name"]
    assert request["restore_staging_path"] == old["restore_staging_path"]


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
