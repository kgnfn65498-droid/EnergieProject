import pathlib
import sys
from dataclasses import dataclass, replace
from types import SimpleNamespace

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, load_mode_state, save_mode_state
import operating_mode_runtime as runtime
from operating_mode_web import _endpoint, render_mode_card
from release_validation_hold import activate_release_hold, load_release_hold


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


class FakeStop:
    def is_set(self):
        return False


def _fake_app(probe_payload=None, probe_error=None):
    state_updates = []
    audits = []

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
        STOP=FakeStop(),
        Handler=object,
        html_page=lambda *args, **kwargs: b"<html><body>ok</body></html>",
        append_audit_event=lambda *args, **kwargs: audits.append((args, kwargs)),
        _state_updates=state_updates,
        _audits=audits,
    )


def _arm_idle_hold(tmp_path, mode=Mode.USER):
    state = replace(
        ModeState.initial(),
        base_mode=mode,
        effective_mode=mode,
        development_session_active=mode is Mode.DEVELOPMENT,
    )
    save_mode_state(tmp_path, state)
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    (tmp_path / "Inbox/processing").mkdir(parents=True, exist_ok=True)
    return state


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


def test_release_validation_has_exactly_five_compact_checks(tmp_path):
    _arm_idle_hold(tmp_path)
    result = runtime.validate_release_hold(_fake_app(), tmp_path, "32.3.14")
    assert set(result["checks"]) == {
        "version",
        "web_runtime",
        "state_io",
        "automatic_runtime_idle",
        "release_chain",
    }
    assert all(check["ok"] for check in result["checks"].values())
    assert result["reconcile_status"] == "ok"


def test_all_green_release_returns_to_persistent_development_not_user(tmp_path):
    _arm_idle_hold(tmp_path, Mode.DEVELOPMENT)
    result = runtime.attempt_release_hold(
        _fake_app(), tmp_path, "32.3.14", issued_by="projectmanager"
    )
    hold = load_release_hold(tmp_path, "32.3.14")
    mode = load_mode_state(tmp_path)
    assert result["status"] == "released"
    assert hold.active is False
    assert mode.base_mode is Mode.DEVELOPMENT
    assert mode.effective_mode is Mode.DEVELOPMENT
    assert mode.development_session_active is True


def test_one_failed_core_check_keeps_hold_active(tmp_path):
    _arm_idle_hold(tmp_path)
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
    result = runtime.attempt_release_hold(app, tmp_path, "32.3.14", issued_by="projectmanager")
    assert result["status"] == "blocked"
    assert result["validation"]["checks"]["automatic_runtime_idle"]["ok"] is False
    assert load_release_hold(tmp_path, "32.3.14").active is True


def test_emergency_release_requires_explicit_confirmation(tmp_path):
    _arm_idle_hold(tmp_path)
    result = runtime.attempt_emergency_release_hold(
        _fake_app(), tmp_path, "32.3.14", issued_by="user", confirmed=False
    )
    assert result["status"] == "confirmation_required"
    assert load_release_hold(tmp_path, "32.3.14").active is True


def test_emergency_release_refuses_running_mutating_workflow(tmp_path):
    _arm_idle_hold(tmp_path)
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
    result = runtime.attempt_emergency_release_hold(
        app, tmp_path, "32.3.14", issued_by="user", confirmed=True
    )
    assert result["status"] == "blocked"
    assert load_release_hold(tmp_path, "32.3.14").active is True


def test_safe_emergency_release_is_persisted_and_audited(tmp_path):
    _arm_idle_hold(tmp_path, Mode.DEVELOPMENT)
    app = _fake_app()
    result = runtime.attempt_emergency_release_hold(
        app, tmp_path, "32.3.14", issued_by="user", confirmed=True
    )
    hold = load_release_hold(tmp_path, "32.3.14")
    mode = load_mode_state(tmp_path)
    assert result["status"] == "released_emergency"
    assert hold.active is False
    assert hold.emergency_release is True
    assert hold.released_by == "user"
    assert app._audits
    assert mode.base_mode is Mode.DEVELOPMENT
    assert mode.development_session_active is True


def test_mode_card_shows_hold_and_validation_status():
    card = render_mode_card({
        "base_mode": "DEVELOPMENT",
        "effective_mode": "DEVELOPMENT",
        "automatic_switching_enabled": True,
        "development_session_active": True,
        "temporary_reason": "",
        "reconciliation_status": "ok",
        "drift": [],
        "desired_profile": {
            "release_ingress_enabled": True,
            "automatic_month_close_enabled": True,
        },
        "release_validation_hold": {
            "active": True,
            "validation_status": "required",
            "reconcile_status": "ok",
        },
    })
    assert "RELEASE VALIDATION HOLD" in card
    assert "AAN" in card
    assert "required" in card


def test_web_exposes_validation_and_emergency_hold_endpoints():
    assert _endpoint("/validate-release-hold") == "validate-release-hold"
    assert _endpoint("/emergency-release-hold") == "emergency-release-hold"
