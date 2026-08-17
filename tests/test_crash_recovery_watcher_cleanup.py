import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/crash_recovery_cleanup.py"
WATCHER = ROOT / "tools/release_watcher.sh"


def run_helper(tmp_path, request):
    project = tmp_path / "EnergieProject"
    (project / "Backups" / "Manifests").mkdir(parents=True, exist_ok=True)
    (project / "Backups" / "RestoreStaging").mkdir(parents=True, exist_ok=True)
    (project / "Inbox").mkdir(parents=True, exist_ok=True)
    request_path = project / "Inbox" / "crash_recovery_cleanup_request.json"
    result_path = project / "Inbox" / "crash_recovery_cleanup_result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "--root",
            str(project),
            "--request",
            str(request_path),
            "--result",
            str(result_path),
        ],
        text=True,
        capture_output=True,
    )
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    return project, proc, result


def valid_request():
    backup_name = "Energie_Complete_Backup_2026_08_20260814T114500Z.zip"
    return {
        "schema": 1,
        "request_id": "cleanup-abc123",
        "backup_name": backup_name,
        "manifest_name": f"{pathlib.Path(backup_name).stem}_manifest.json",
        "restore_staging_path": "/recovery/RestoreStaging/2026_08_20260814T114556Z",
    }


def seed_targets(project, request):
    backup = project / "Backups" / request["backup_name"]
    manifest = project / "Backups" / "Manifests" / request["manifest_name"]
    staging = project / "Backups" / "RestoreStaging" / pathlib.Path(request["restore_staging_path"]).name
    backup.write_bytes(b"backup")
    manifest.write_text("{}", encoding="utf-8")
    staging.mkdir(parents=True)
    (staging / "restored.txt").write_text("ok", encoding="utf-8")
    return backup, manifest, staging


def test_helper_removes_only_exact_run_artifacts_and_is_idempotent(tmp_path):
    request = valid_request()
    project = tmp_path / "EnergieProject"
    (project / "Backups" / "Manifests").mkdir(parents=True)
    (project / "Backups" / "RestoreStaging").mkdir(parents=True)
    (project / "Inbox").mkdir(parents=True)
    backup, manifest, staging = seed_targets(project, request)

    keep_month = project / "Backups" / "EnergieProject_maandbackup_2026_07.zip"
    keep_full = project / "Backups" / "FULL_RECOVERY_old.tar.gz"
    keep_release = project / "Inbox" / "EnergieProject_v32.0.31.zip"
    keep_month.write_bytes(b"keep")
    keep_full.write_bytes(b"keep")
    keep_release.write_bytes(b"keep")

    request_path = project / "Inbox" / "crash_recovery_cleanup_request.json"
    result_path = project / "Inbox" / "crash_recovery_cleanup_result.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(HELPER), "--root", str(project), "--request", str(request_path), "--result", str(result_path)],
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["request_id"] == request["request_id"]
    assert not backup.exists()
    assert not manifest.exists()
    assert not staging.exists()
    assert keep_month.exists()
    assert keep_full.exists()
    assert keep_release.exists()

    proc2 = subprocess.run(
        [sys.executable, str(HELPER), "--root", str(project), "--request", str(request_path), "--result", str(result_path)],
        text=True,
        capture_output=True,
    )
    assert proc2.returncode == 0, proc2.stderr
    result2 = json.loads(result_path.read_text(encoding="utf-8"))
    assert result2["status"] == "ok"
    assert len(result2["already_absent"]) == 3


def test_helper_rejects_month_backup_and_preserves_everything(tmp_path):
    request = valid_request()
    request["backup_name"] = "EnergieProject_maandbackup_2026_07.zip"
    request["manifest_name"] = "EnergieProject_maandbackup_2026_07_manifest.json"
    project, proc, result = run_helper(tmp_path, request)
    assert proc.returncode != 0
    assert result["status"] == "error"
    assert "backup" in result["error"].lower()


def test_helper_rejects_full_recovery_and_path_traversal(tmp_path):
    for backup_name, staging_path in [
        ("FULL_RECOVERY_old.tar.gz", "/recovery/RestoreStaging/run-1"),
        ("Energie_Complete_Backup_2026_08_test.zip", "/recovery/RestoreStaging/../../outside"),
        ("Energie_Complete_Backup_2026_08_test.zip", "/recovery/RestoreStaging"),
    ]:
        request = valid_request()
        request["backup_name"] = backup_name
        request["manifest_name"] = f"{pathlib.Path(backup_name).stem}_manifest.json"
        request["restore_staging_path"] = staging_path
        project, proc, result = run_helper(tmp_path, request)
        assert proc.returncode != 0
        assert result["status"] == "error"


def test_helper_rejects_manifest_not_derived_from_backup(tmp_path):
    request = valid_request()
    request["manifest_name"] = "historische_maand_manifest.json"
    project, proc, result = run_helper(tmp_path, request)
    assert proc.returncode != 0
    assert result["status"] == "error"
    assert "manifest" in result["error"].lower()


def test_release_watcher_processes_cleanup_request_only_behind_maintenance_gate():
    source = WATCHER.read_text(encoding="utf-8")
    assert 'CRASH_CLEANUP_REQUEST="$INBOX/crash_recovery_cleanup_request.json"' in source
    assert 'CRASH_CLEANUP_RESULT="$INBOX/crash_recovery_cleanup_result.json"' in source
    assert 'CRASH_CLEANUP_HELPER="$PROJECT/tools/crash_recovery_cleanup.py"' in source
    assert "process_crash_recovery_cleanup" in source
    loop = source.split("while :; do", 1)[1]
    assert loop.index("mode_allows maintenance_requests") < loop.index("process_crash_recovery_cleanup")
    assert loop.index("process_crash_recovery_cleanup") < loop.index("mode_allows release_ingress")
    assert loop.index("mode_allows release_ingress") < loop.index('set -- "$INCOMING"/*.zip')
