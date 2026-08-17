import json
import pathlib
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, load_mode_state, profile_for, save_mode_state
import operating_mode_crash_recovery as crash_mode


AUTOMATIC_MUTATIONS = ("schedule", "full_workflow", "automatic_month_close")


def _state_for(base: Mode) -> ModeState:
    return replace(
        ModeState.initial(),
        base_mode=base,
        effective_mode=base,
        development_session_active=base is Mode.DEVELOPMENT,
    )


@pytest.mark.parametrize("base", [Mode.USER, Mode.DEVELOPMENT])
def test_backup_verify_session_suspends_all_automatic_mutation_features(tmp_path, base):
    save_mode_state(tmp_path, _state_for(base))

    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="backup_verify")
    during = load_mode_state(tmp_path)
    profile = profile_for(during.effective_mode, during.suspended_features)

    assert during.base_mode is base
    assert during.effective_mode is Mode.MAINTENANCE
    assert during.suspended_features == AUTOMATIC_MUTATIONS
    assert profile.schedule_enabled is False
    assert profile.full_workflow_enabled is False
    assert profile.automatic_month_close_enabled is False


@pytest.mark.parametrize("base", [Mode.USER, Mode.DEVELOPMENT])
def test_mutating_cleanup_session_also_suspends_automatic_mutations(tmp_path, base):
    save_mode_state(tmp_path, _state_for(base))

    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="mutating_maintenance")
    during = load_mode_state(tmp_path)

    assert during.effective_mode is Mode.MAINTENANCE
    assert during.suspended_features == AUTOMATIC_MUTATIONS


def _cleanup_app(tmp_path, cleanup_result):
    app = SimpleNamespace()
    app.run_complete_crash_recovery = lambda: {"status": "verified"}
    app.run_complete_restore_staging = lambda: {"status": "staged", "source_project_modified": False}
    app.run_complete_crash_recovery_export = lambda: {"status": "ready_for_download", "source_project_modified": False}
    app._cleanup_completed_export = lambda state: dict(cleanup_result)
    app.CRASH_RECOVERY_CLEANUP_RESULT_PATH = tmp_path / "Inbox/crash_recovery_cleanup_result.json"
    return app


def test_post_download_cleanup_keeps_maintenance_until_matching_watcher_ok(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    app = _cleanup_app(tmp_path, {"status": "pending_watcher", "request_id": "req-ok"})
    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)

    result = app._cleanup_completed_export({"download_status": "downloaded"})
    pending = load_mode_state(tmp_path)
    session = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))

    assert result["status"] == "pending_watcher"
    assert pending.base_mode is Mode.DEVELOPMENT
    assert pending.effective_mode is Mode.MAINTENANCE
    assert pending.development_session_active is True
    assert session["phase"] == "waiting_cleanup"
    assert session["cleanup_request_id"] == "req-ok"

    app.CRASH_RECOVERY_CLEANUP_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.CRASH_RECOVERY_CLEANUP_RESULT_PATH.write_text(
        json.dumps({"request_id": "req-ok", "status": "ok", "removed": ["backup"]}),
        encoding="utf-8",
    )
    reconciled = crash_mode.reconcile_pending_crash_recovery_cleanup(app, tmp_path)
    final = load_mode_state(tmp_path)

    assert reconciled["status"] == "completed"
    assert reconciled["outcome"] == "pass"
    assert final.base_mode is Mode.DEVELOPMENT
    assert final.effective_mode is Mode.DEVELOPMENT
    assert final.development_session_active is True


def test_post_download_cleanup_error_stays_maintenance_as_unsafe(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.USER))
    app = _cleanup_app(tmp_path, {"status": "pending_watcher", "request_id": "req-bad"})
    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)
    app._cleanup_completed_export({"download_status": "downloaded"})

    app.CRASH_RECOVERY_CLEANUP_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.CRASH_RECOVERY_CLEANUP_RESULT_PATH.write_text(
        json.dumps({"request_id": "req-bad", "status": "error", "error": "partial cleanup"}),
        encoding="utf-8",
    )
    reconciled = crash_mode.reconcile_pending_crash_recovery_cleanup(app, tmp_path)
    final = load_mode_state(tmp_path)
    session = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))

    assert reconciled["status"] == "unsafe_hold"
    assert final.base_mode is Mode.USER
    assert final.effective_mode is Mode.MAINTENANCE
    assert final.active_transition_id
    assert session["phase"] == "unsafe_hold"
    assert session["outcome"] == "unsafe"


def test_reboot_while_cleanup_waits_preserves_maintenance_for_result_reconcile(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="mutating_maintenance")
    crash_mode.mark_crash_recovery_cleanup_pending(tmp_path, "req-reboot")

    recovery = crash_mode.recover_crash_recovery_mode_session(tmp_path)
    state = load_mode_state(tmp_path)
    session = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))

    assert recovery["status"] == "waiting_cleanup"
    assert recovery["preserve_temporary"] is True
    assert state.effective_mode is Mode.MAINTENANCE
    assert state.base_mode is Mode.DEVELOPMENT
    assert session["phase"] == "waiting_cleanup"
    assert session["cleanup_request_id"] == "req-reboot"


def test_mode_entrypoint_runs_cleanup_reconciler_periodically():
    text = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert "crash_recovery_mode_worker" in text
