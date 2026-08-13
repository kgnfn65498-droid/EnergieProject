import importlib.util
import json
import pathlib
import sys


def load_main():
    source = pathlib.Path(__file__).parents[1] / "slimmemeterportal_import/rootfs/app/main.py"
    spec = importlib.util.spec_from_file_location("energy_complete_recovery_runtime", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_recovery_uses_preview_create_deep_verify_only(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "complete_crash_recovery_state.json"
    calls = []

    def fake_action(name, arguments, timeout=8.0):
        calls.append((name, dict(arguments)))
        if name == "preview_month_closure":
            return {"confirmation": "BEVESTIG COMPLETE BACKUP"}
        if name == "create_complete_backup":
            return {
                "status": "ok",
                "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip",
            }
        if name == "verify_complete_backup":
            return {
                "status": "valid",
                "deep_verified": True,
                "manifest_file_count": 1216,
                "verified_files": 1216,
                "hash_failures": [],
                "sha256": "abc123",
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_crash_recovery(year=2026, month=8)

    assert result["status"] == "verified"
    assert [name for name, _ in calls] == [
        "preview_month_closure",
        "create_complete_backup",
        "verify_complete_backup",
    ]
    assert calls[-1][1]["deep_verify_files"] is True
    assert "finalize_month" not in [name for name, _ in calls]


def test_complete_recovery_refuses_active_workflow(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    class Locked:
        @staticmethod
        def locked():
            return True

    monkeypatch.setattr(m, "WORKFLOW_LOCK", Locked())
    result = m.run_complete_crash_recovery(year=2026, month=8)

    assert result["status"] == "busy"


def test_complete_recovery_does_not_mark_bad_verify_as_good(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    def fake_action(name, arguments, timeout=8.0):
        if name == "preview_month_closure":
            return {"confirmation": "BEVESTIG"}
        if name == "create_complete_backup":
            return {"backup": "/recovery/Energie_Complete_Backup_2026_08_bad.zip"}
        if name == "verify_complete_backup":
            return {
                "status": "valid",
                "deep_verified": True,
                "manifest_file_count": 1216,
                "verified_files": 1215,
                "hash_failures": [],
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_crash_recovery(year=2026, month=8)

    assert result["status"] == "error"
    assert result["deep_verified"] is False


def test_restore_test_accepts_only_isolated_staging(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.write_atomic_json(
        m.COMPLETE_CRASH_RECOVERY_STATE_PATH,
        {
            "status": "verified",
            "backup_name": "Energie_Complete_Backup_2026_08_test.zip",
            "year": 2026,
            "month": 8,
        },
    )
    calls = []

    def fake_action(name, arguments, timeout=8.0):
        calls.append(name)
        if name == "preview_backup_restore":
            return {"confirmation": "BEVESTIG HERSTELTEST"}
        if name == "stage_backup_restore":
            return {
                "status": "staged",
                "staging_path": "/recovery/RestoreStaging/Energie_Complete_Backup_2026_08_test",
                "source_project_modified": False,
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_restore_staging()

    assert result["status"] == "staged"
    assert result["source_project_modified"] is False
    assert calls == ["preview_backup_restore", "stage_backup_restore"]


def test_restore_test_rejects_any_production_modification_signal(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.write_atomic_json(
        m.COMPLETE_CRASH_RECOVERY_STATE_PATH,
        {
            "status": "verified",
            "backup_name": "Energie_Complete_Backup_2026_08_test.zip",
            "year": 2026,
            "month": 8,
        },
    )

    def fake_action(name, arguments, timeout=8.0):
        if name == "preview_backup_restore":
            return {"confirmation": "BEVESTIG HERSTELTEST"}
        if name == "stage_backup_restore":
            return {
                "status": "staged",
                "staging_path": "/recovery/RestoreStaging/test",
                "source_project_modified": True,
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_restore_staging()

    assert result["status"] == "error"


def test_complete_recovery_state_contains_no_confirmation_secret(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    def fake_action(name, arguments, timeout=8.0):
        if name == "preview_month_closure":
            return {"confirmation": "UNIQUE-CONFIRMATION-TEXT"}
        if name == "create_complete_backup":
            return {"backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip"}
        if name == "verify_complete_backup":
            return {
                "status": "valid",
                "deep_verified": True,
                "manifest_file_count": 1,
                "verified_files": 1,
                "hash_failures": [],
                "sha256": "abc",
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    m.run_complete_crash_recovery(year=2026, month=8)

    raw = m.COMPLETE_CRASH_RECOVERY_STATE_PATH.read_text(encoding="utf-8")
    assert "UNIQUE-CONFIRMATION-TEXT" not in raw
    json.loads(raw)
