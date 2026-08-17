import json
import pathlib
import sys

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, save_mode_state
from operating_mode_runtime import operating_mode_tick, reconcile_state


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
    assert "operating-mode-reconcile" in entry
