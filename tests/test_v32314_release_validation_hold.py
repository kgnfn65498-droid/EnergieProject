import json
import pathlib
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from zoneinfo import ZoneInfo

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, command_path, process_mode_command
import operating_mode_runtime as mode_runtime
from operating_mode_runtime import recover_startup_mode_state
from release_validation_hold import (
    activate_release_hold,
    hold_state_path,
    load_release_hold,
)


def test_release_hold_persists_across_reload(tmp_path):
    state = activate_release_hold(tmp_path, "32.3.14", "release_install")
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert state.active is True
    assert loaded.active is True
    assert loaded.release_version == "32.3.14"
    assert loaded.activated_reason == "release_install"


def test_missing_hold_state_for_new_release_is_fail_closed(tmp_path):
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert loaded.active is True
    assert loaded.validation_status == "required"
    assert "missing_hold_state" in loaded.reasons


def test_corrupt_hold_state_is_fail_closed(tmp_path):
    path = hold_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert loaded.active is True
    assert loaded.validation_status == "required"
    assert "invalid_hold_state" in loaded.reasons


def _write_mode_command(tmp_path, payload):
    path = command_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_set_base_development_opens_persistent_development_session(tmp_path):
    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-open-1",
        "action": "set_base",
        "requested_mode": "DEVELOPMENT",
        "issued_by": "projectmanager",
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.development_session_active is True

    recovered = recover_startup_mode_state(tmp_path)
    assert recovered.base_mode is Mode.DEVELOPMENT
    assert recovered.effective_mode is Mode.DEVELOPMENT
    assert recovered.development_session_active is True


def test_plain_user_mode_change_cannot_close_development_session(tmp_path):
    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-open-2",
        "action": "set_base",
        "requested_mode": "DEVELOPMENT",
        "issued_by": "projectmanager",
    })
    process_mode_command(tmp_path)

    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "accidental-user-1",
        "action": "set_base",
        "requested_mode": "USER",
        "issued_by": "runtime",
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.development_session_active is True
    assert "development_session_requires_explicit_close" in state.drift


def test_only_user_confirmed_close_ends_development_session(tmp_path):
    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-open-3",
        "action": "set_base",
        "requested_mode": "DEVELOPMENT",
        "issued_by": "projectmanager",
    })
    process_mode_command(tmp_path)

    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-close-denied",
        "action": "close_development_session",
        "issued_by": "projectmanager",
        "confirmed_by_user": False,
    })
    denied = process_mode_command(tmp_path)
    assert denied.base_mode is Mode.DEVELOPMENT
    assert denied.development_session_active is True

    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-close-confirmed",
        "action": "close_development_session",
        "issued_by": "projectmanager",
        "confirmed_by_user": True,
    })
    closed = process_mode_command(tmp_path)
    assert closed.base_mode is Mode.USER
    assert closed.effective_mode is Mode.USER
    assert closed.development_session_active is False


def test_release_hold_does_not_change_persistent_development_session(tmp_path):
    _write_mode_command(tmp_path, {
        "schema_version": 1,
        "request_id": "dev-open-4",
        "action": "set_base",
        "requested_mode": "DEVELOPMENT",
        "issued_by": "projectmanager",
    })
    process_mode_command(tmp_path)
    activate_release_hold(tmp_path, "32.3.14", "release_install")

    recovered = recover_startup_mode_state(tmp_path)
    assert recovered.base_mode is Mode.DEVELOPMENT
    assert recovered.effective_mode is Mode.DEVELOPMENT
    assert recovered.development_session_active is True
    assert load_release_hold(tmp_path, "32.3.14").active is True


@dataclass(frozen=True)
class FakeOptions:
    run_on_start: bool = True
    schedule_enabled: bool = True
    full_workflow_enabled: bool = True
    automatic_month_close_enabled: bool = True


def test_hold_forces_all_automatic_mutating_options_off(tmp_path):
    hold = activate_release_hold(tmp_path, "32.3.14", "release_install")
    effective = mode_runtime.effective_options_for_runtime(FakeOptions(), ModeState.initial(), hold)
    assert effective.run_on_start is False
    assert effective.schedule_enabled is False
    assert effective.full_workflow_enabled is False
    assert effective.automatic_month_close_enabled is False


def test_automatic_month_close_execute_guard_blocks_even_with_stale_enabled_options(tmp_path):
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    calls = []
    audits = []

    class FakeOptionsLoader:
        @classmethod
        def load(cls):
            return FakeOptions()

    def raw_execute(options, month_key, *args, **kwargs):
        calls.append((options, month_key, args, kwargs))
        return {"status": "raw_called"}

    fake_app = SimpleNamespace(
        APP_VERSION="32.3.14",
        TZ=ZoneInfo("Europe/Amsterdam"),
        Options=FakeOptionsLoader,
        execute_automatic_month_close=raw_execute,
        append_audit_event=lambda *args, **kwargs: audits.append((args, kwargs)),
        LOGGER=SimpleNamespace(exception=lambda *args, **kwargs: None),
    )

    mode_runtime.install_release_hold_guards(fake_app, tmp_path)
    result = fake_app.execute_automatic_month_close(FakeOptions(), "2026_07", trigger="automatic")
    assert result["status"] == "blocked_release_validation_hold"
    assert calls == []
    assert audits


def test_release_hold_guards_are_installed_before_app_main_starts_scheduler():
    text = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert "install_release_hold_guards" in text
    assert text.index("install_release_hold_guards(app, root)") < text.index("app.main()")
