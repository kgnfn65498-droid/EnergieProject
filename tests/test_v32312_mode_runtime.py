import json
import pathlib
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from zoneinfo import ZoneInfo

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, save_mode_state
from operating_mode_runtime import (
    effective_options_for_mode,
    is_fully_closed_month,
    mode_history_path,
    operating_mode_tick,
    reconcile_state,
)


def test_reconcile_marks_matching_user_profile_ok(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    observed = {
        "release_ingress_enabled": False,
        "maintenance_request_processing_enabled": False,
        "schedule_enabled": True,
        "full_workflow_enabled": True,
        "automatic_month_close_enabled": True,
    }
    state = reconcile_state(tmp_path, observed)
    assert state.reconciliation_status == "ok"
    assert state.drift == ()


def test_reconcile_records_drift(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    state = reconcile_state(tmp_path, {"release_ingress_enabled": True})
    assert state.reconciliation_status == "drift"
    assert any("release_ingress_enabled" in item for item in state.drift)


def test_operating_mode_tick_processes_projectmanager_command(tmp_path):
    command = tmp_path / "Data/03_Systeem/Projectmanager/State/operating_mode_command.json"
    command.parent.mkdir(parents=True, exist_ok=True)
    command.write_text(json.dumps({
        "schema_version": 1,
        "request_id": "runtime-1",
        "action": "begin_temporary",
        "requested_mode": "DEVELOPMENT",
        "reason": "runtime test",
        "issued_by": "test",
    }), encoding="utf-8")
    snapshot = operating_mode_tick(tmp_path)
    assert snapshot["effective_mode"] == Mode.DEVELOPMENT.value
    assert snapshot["last_processed_request_id"] == "runtime-1"
    assert snapshot["reconciliation_status"] == "ok"


def test_addon_launcher_uses_mode_entrypoint_before_main():
    root = pathlib.Path(__file__).resolve().parents[1]
    run_sh = (root / "slimmemeterportal_import/run.sh").read_text(encoding="utf-8")
    entry = (root / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert "exec python3 -u /app/mode_entrypoint.py" in run_sh
    assert entry.index("operating_mode_tick(root)") < entry.index("app.main()")
    assert entry.index("install_mode_overrides(app, root)") < entry.index("app.main()")
    assert entry.index("install_mode_web(app, root)") < entry.index("app.main()")
    assert "operating-mode-reconcile" in entry


@dataclass(frozen=True)
class FakeOptions:
    schedule_enabled: bool
    full_workflow_enabled: bool
    automatic_month_close_enabled: bool


def test_user_overrides_stale_disabled_month_switches():
    options = FakeOptions(False, False, False)
    effective = effective_options_for_mode(options, ModeState.initial())
    assert effective.schedule_enabled is True
    assert effective.full_workflow_enabled is True
    assert effective.automatic_month_close_enabled is True


def test_current_month_is_never_fully_closed():
    now = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    assert is_fully_closed_month("2026_08", now) is False
    assert is_fully_closed_month("2026_07", now) is True


def test_maintenance_pause_is_restored_by_profile():
    state = replace(
        ModeState.initial(),
        effective_mode=Mode.MAINTENANCE,
        suspended_features=("automatic_month_close",),
    )
    paused = effective_options_for_mode(FakeOptions(True, True, True), state)
    assert paused.automatic_month_close_enabled is False
    restored = effective_options_for_mode(
        FakeOptions(True, True, False),
        replace(state, suspended_features=()),
    )
    assert restored.automatic_month_close_enabled is True


def test_accepted_command_appends_exactly_one_mode_history_event(tmp_path):
    command = tmp_path / "Data/03_Systeem/Projectmanager/State/operating_mode_command.json"
    command.parent.mkdir(parents=True, exist_ok=True)
    command.write_text(json.dumps({
        "schema_version": 1,
        "request_id": "audit-1",
        "action": "begin_temporary",
        "requested_mode": "DEVELOPMENT",
        "reason": "build",
        "issued_by": "chatgpt_projectmanager",
    }), encoding="utf-8")
    operating_mode_tick(tmp_path)
    operating_mode_tick(tmp_path)
    lines = mode_history_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["request_id"] == "audit-1"
    assert event["issued_by"] == "chatgpt_projectmanager"
    assert event["from_effective_mode"] == "USER"
    assert event["to_effective_mode"] == "DEVELOPMENT"
    assert event["reason"] == "build"
    assert event["reconciliation_status"] == "ok"
