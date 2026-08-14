import importlib.util
import inspect
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def real_backend_action_factory(calls):
    def action(name, arguments, timeout=8.0):
        calls.append((name, dict(arguments)))

        if name == "preview_month_closure":
            return {
                "operation": "preview_month_closure",
                "confirmation_required": "SLUIT 2026_08 AF",
            }

        if name == "create_complete_backup":
            return {
                "status": "created",
                "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip",
                "sha256": "created-sha",
            }

        if name == "verify_complete_backup":
            return {
                "status": "valid",
                "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip",
                "backup_sha256": "REAL-SHA256",
                "entries": 1217,
                "manifest_file_count": 1216,
                "zip_integrity": "ok",
                "deep_verified": True,
                "verified_files": 1216,
                "hash_failures": [],
            }

        if name == "preview_backup_restore":
            return {
                "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip",
                "entries": 1217,
                "staging_root": "/recovery/RestoreStaging",
                "project_root_writable": False,
                "confirmation_required": "STAGE HERSTEL 2026_08",
            }

        if name == "stage_backup_restore":
            return {
                "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip",
                "staging": "/recovery/RestoreStaging/test",
                "extracted": 1217,
                "source_project_modified": False,
            }

        raise AssertionError(name)

    return action


def test_complete_recovery_real_backend_contract(monkeypatch, tmp_path):
    m = load_main("recovery_complete_contract")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    calls = []
    monkeypatch.setattr(
        m,
        "_mcp_call_project_action",
        real_backend_action_factory(calls),
    )

    result = m.run_complete_crash_recovery(2026, 8)

    assert result["status"] == "verified"
    assert result["sha256"] == "REAL-SHA256"
    assert result["manifest_file_count"] == 1216
    assert result["verified_files"] == 1216
    assert result["hash_failures"] == []
    assert result["deep_verified"] is True

    assert [x[0] for x in calls] == [
        "preview_month_closure",
        "create_complete_backup",
        "verify_complete_backup",
    ]

    assert calls[-1][1]["deep_verify_files"] is True


def test_incomplete_verify_is_rejected(monkeypatch, tmp_path):
    m = load_main("recovery_bad_verify")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    def action(name, arguments, timeout=8.0):
        if name == "preview_month_closure":
            return {"confirmation_required": "SLUIT 2026_08 AF"}
        if name == "create_complete_backup":
            return {
                "backup": "/recovery/Energie_Complete_Backup_bad.zip"
            }
        if name == "verify_complete_backup":
            return {
                "status": "valid",
                "deep_verified": True,
                "manifest_file_count": 1216,
                "verified_files": 1215,
                "hash_failures": [],
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", action)

    result = m.run_complete_crash_recovery(2026, 8)
    assert result["status"] == "error"


def test_real_restore_contract_only_accepts_restorestaging(
    monkeypatch,
    tmp_path,
):
    m = load_main("recovery_restore_contract")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    m.write_atomic_json(
        m.COMPLETE_CRASH_RECOVERY_STATE_PATH,
        {
            "status": "verified",
            "deep_verified": True,
            "backup_name": "Energie_Complete_Backup_test.zip",
            "year": 2026,
            "month": 8,
        },
    )

    calls = []
    monkeypatch.setattr(
        m,
        "_mcp_call_project_action",
        real_backend_action_factory(calls),
    )

    result = m.run_complete_restore_staging()

    assert result["status"] == "staged"
    assert result["staging_path"].startswith(
        "/recovery/RestoreStaging/"
    )
    assert result["source_project_modified"] is False


def test_export_flow_runs_existing_verify_then_restore_then_export(monkeypatch, tmp_path):
    m = load_main("recovery_export_flow")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"
    m.NAS_LAYOUT_ROOT = tmp_path / "EnergieProject"

    calls = []

    def complete(year=None, month=None):
        calls.append("complete")
        return {
            "status": "verified",
            "version": m.APP_VERSION,
            "year": 2026,
            "month": 8,
            "backup_name": "Energie_Complete_Backup_2026_08_test.zip",
            "sha256": "BACKUP-SHA",
            "manifest_file_count": 1267,
            "verified_files": 1267,
            "hash_failures": [],
            "deep_verified": True,
        }

    def stage():
        calls.append("stage")
        return {
            "status": "staged",
            "backup_name": "Energie_Complete_Backup_2026_08_test.zip",
            "staging_path": "/recovery/RestoreStaging/test",
            "source_project_modified": False,
        }

    def build(project_root, output_zip):
        calls.append("build")
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        output_zip.write_bytes(b"ZIP")
        return types.SimpleNamespace(
            zip_path=output_zip,
            file_count=1400,
            total_bytes=123456,
            sha256="A" * 64,
        )

    def verify(path):
        calls.append("verify_export")
        return types.SimpleNamespace(
            valid=True,
            file_count=1400,
            sha256="A" * 64,
            top_level_ok=True,
            required_roots_ok=True,
            excluded_hits=(),
            error="",
        )

    monkeypatch.setattr(m, "run_complete_crash_recovery", complete)
    monkeypatch.setattr(m, "run_complete_restore_staging", stage)
    monkeypatch.setattr(m, "build_recovery_export", build)
    monkeypatch.setattr(m, "verify_recovery_export", verify)

    result = m.run_complete_crash_recovery_export(2026, 8)

    assert result["status"] == "ready_for_download"
    assert result["backup_name"] == "Energie_Complete_Backup_2026_08_test.zip"
    assert result["backup_sha256"] == "BACKUP-SHA"
    assert result["manifest_file_count"] == 1267
    assert result["verified_files"] == 1267
    assert result["restore_test_status"] == "staged"
    assert result["source_project_modified"] is False
    assert result["export_file_count"] == 1400
    assert result["export_sha256"] == "A" * 64
    assert result["download_status"] == "ready"
    assert result["cleanup_status"] == "pending"
    assert calls == ["complete", "stage", "build", "verify_export"]


def test_export_flow_rejects_unsafe_restore_before_build(monkeypatch, tmp_path):
    m = load_main("recovery_export_unsafe_stage")
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.CRASH_RECOVERY_EXPORT_ROOT = tmp_path / "exports"

    monkeypatch.setattr(
        m,
        "run_complete_crash_recovery",
        lambda year=None, month=None: {
            "status": "verified",
            "year": 2026,
            "month": 8,
            "backup_name": "Energie_Complete_Backup_test.zip",
            "sha256": "BACKUP-SHA",
            "manifest_file_count": 10,
            "verified_files": 10,
            "hash_failures": [],
            "deep_verified": True,
        },
    )
    monkeypatch.setattr(
        m,
        "run_complete_restore_staging",
        lambda: {
            "status": "staged",
            "staging_path": "/tmp/not-safe",
            "source_project_modified": False,
        },
    )

    def should_not_build(*args, **kwargs):
        raise AssertionError("export build mag niet starten na onveilige RestoreStaging")

    monkeypatch.setattr(m, "build_recovery_export", should_not_build)

    result = m.run_complete_crash_recovery_export(2026, 8)
    assert result["status"] == "error"
    assert "RestoreStaging" in result["error"]


def test_recovery_route_never_finalizes_month():
    m = load_main("recovery_no_finalize")

    code = (
        inspect.getsource(m.run_complete_crash_recovery)
        + inspect.getsource(m.run_complete_restore_staging)
    )
    if hasattr(m, "run_complete_crash_recovery_export"):
        code += inspect.getsource(m.run_complete_crash_recovery_export)

    assert "finalize_month" not in code


def test_gui_and_http_routes_present():
    source = MAIN.read_text(encoding="utf-8")

    for required in (
        "Complete Crash Recovery",
        "Maak complete Crash Recovery",
        "Test herstel naar RestoreStaging",
        "/api/crash-recovery/state",
        "/api/crash-recovery/complete",
        "/api/crash-recovery/stage",
    ):
        assert required in source


def test_v32029_export_routes_and_download_ui_are_present():
    source = MAIN.read_text(encoding="utf-8")

    for required in (
        "/api/crash-recovery/export",
        "/api/crash-recovery/download",
        "Download Crash Recovery ZIP",
        "ready_for_download",
    ):
        assert required in source
