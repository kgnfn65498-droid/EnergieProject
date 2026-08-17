import pathlib
import sys
from dataclasses import dataclass
from types import SimpleNamespace

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import ModeState, load_mode_state, save_mode_state
import operating_mode_runtime as runtime
from release_validation_hold import activate_release_hold


@dataclass(frozen=True)
class FakeOptions:
    run_on_start: bool = False
    schedule_enabled: bool = False
    full_workflow_enabled: bool = False
    automatic_month_close_enabled: bool = False


class FakeOptionsLoader:
    @classmethod
    def load(cls):
        return FakeOptions()


def _fake_app(probe_payload=None, probe_error=None):
    state_updates = []

    def probe():
        if probe_error is not None:
            raise probe_error
        return dict(probe_payload or {
            "workflow_running": False,
            "workflow_active": {},
            "cancel_requested": False,
            "run_on_start_effective": False,
            "schedule_effective": False,
            "full_workflow_effective": False,
            "automatic_month_close_effective": False,
            "release_processing": [],
        })

    def update_state(**kwargs):
        state_updates.append(dict(kwargs))

    return SimpleNamespace(
        APP_VERSION="32.3.14",
        operating_runtime_probe=probe,
        update_state=update_state,
        Options=FakeOptionsLoader,
        _state_updates=state_updates,
    )


def test_observer_reports_real_running_workflow(tmp_path):
    hold = activate_release_hold(tmp_path, "32.3.14", "release_install")
    app = _fake_app({
        "workflow_running": True,
        "workflow_active": {"month": "2026_07", "trigger": "automatic"},
        "cancel_requested": False,
        "run_on_start_effective": False,
        "schedule_effective": False,
        "full_workflow_effective": False,
        "automatic_month_close_effective": False,
        "release_processing": [],
    })
    observed = runtime.observe_measured_runtime(app, tmp_path, ModeState.initial(), hold)
    assert observed["workflow_running"] is True
    assert observed["workflow_active"]["month"] == "2026_07"


def test_hold_plus_running_workflow_is_drift_and_requests_controlled_cancel(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    app = _fake_app({
        "workflow_running": True,
        "workflow_active": {"month": "2026_07", "trigger": "automatic"},
        "cancel_requested": False,
        "run_on_start_effective": False,
        "schedule_effective": False,
        "full_workflow_effective": False,
        "automatic_month_close_effective": False,
        "release_processing": [],
    })

    state = runtime.reconcile_measured_runtime(tmp_path, app)

    assert state.reconciliation_status == "drift"
    assert "workflow_running_during_release_hold" in state.drift
    assert any(update.get("cancel_requested") is True for update in app._state_updates)
    assert any(update.get("workflow_cancel_reason") == "release_validation_hold_drift" for update in app._state_updates)


def test_unreadable_runtime_never_reports_reconcile_ok(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    app = _fake_app(probe_error=RuntimeError("probe unavailable"))

    state = runtime.reconcile_measured_runtime(tmp_path, app)

    assert state.reconciliation_status != "ok"
    assert state.reconciliation_status == "required"
    assert any("runtime_probe_unavailable" in item for item in state.drift)


def test_live_tick_uses_measured_runtime_not_desired_profile(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    app = _fake_app({
        "workflow_running": True,
        "workflow_active": {"month": "2026_07"},
        "cancel_requested": False,
        "run_on_start_effective": False,
        "schedule_effective": False,
        "full_workflow_effective": False,
        "automatic_month_close_effective": False,
        "release_processing": [],
    })

    snapshot = runtime.operating_mode_tick(tmp_path, app_module=app)

    assert snapshot["reconciliation_status"] == "drift"
    assert "workflow_running_during_release_hold" in snapshot["drift"]


def test_hold_idle_runtime_can_reconcile_ok_after_real_probe(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    app = _fake_app()

    state = runtime.reconcile_measured_runtime(tmp_path, app)

    assert state.reconciliation_status == "ok"
    assert state.observed_profile["workflow_running"] is False
