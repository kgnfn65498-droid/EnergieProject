from dataclasses import replace
import json
import pathlib
import sys

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import (
    Mode,
    ModeState,
    format_chat_status,
    load_mode_state,
    profile_for,
    save_mode_state,
)


def test_missing_state_migrates_to_safe_user(tmp_path):
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.USER
    assert state.automatic_switching_enabled is True
    assert state.reconciliation_status == "required"


def test_invalid_state_fails_closed_to_user(tmp_path):
    path = tmp_path / "Inbox/operating_mode/operating_mode_state.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"base_mode":"BROKEN"}', encoding="utf-8")
    state = load_mode_state(tmp_path)
    assert state.effective_mode is Mode.USER
    assert state.reconciliation_status == "required"
    assert state.drift


def test_profiles_match_approved_contract():
    user = profile_for(Mode.USER)
    dev = profile_for(Mode.DEVELOPMENT)
    maint = profile_for(Mode.MAINTENANCE)
    assert user.release_ingress_enabled is False
    assert user.maintenance_request_processing_enabled is False
    assert user.schedule_enabled is True
    assert user.full_workflow_enabled is True
    assert user.automatic_month_close_enabled is True
    assert dev.release_ingress_enabled is True
    assert dev.maintenance_request_processing_enabled is False
    assert maint.release_ingress_enabled is False
    assert maint.maintenance_request_processing_enabled is True


def test_atomic_roundtrip_preserves_state(tmp_path):
    original = ModeState.initial()
    changed = replace(original, base_mode=Mode.DEVELOPMENT, effective_mode=Mode.DEVELOPMENT)
    save_mode_state(tmp_path, changed)
    assert load_mode_state(tmp_path) == changed


def test_chat_status_shows_base_effective_auto_and_reason():
    state = replace(
        ModeState.initial(),
        effective_mode=Mode.MAINTENANCE,
        temporary_reason="backup uitvoeren",
    )
    assert format_chat_status(state) == "[MODE] MAINTENANCE · AUTO AAN · basis USER · backup uitvoeren"


from operating_modes import command_path, process_mode_command


def write_command(root, payload):
    path = command_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_begin_temporary_development_preserves_user_base(tmp_path):
    write_command(tmp_path, {
        "schema_version": 1,
        "request_id": "req-1",
        "action": "begin_temporary",
        "requested_mode": "DEVELOPMENT",
        "reason": "mode controller bouwen",
        "issued_by": "chatgpt_projectmanager",
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.active_transition_id == "req-1"


def test_end_temporary_returns_to_base(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "begin_temporary", "requested_mode": "MAINTENANCE", "reason": "backup"})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "end_temporary", "transition_id": "req-1"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.USER
    assert state.active_transition_id == ""


def test_replayed_request_is_idempotent(tmp_path):
    payload = {"schema_version": 1, "request_id": "req-1", "action": "set_base", "requested_mode": "DEVELOPMENT"}
    write_command(tmp_path, payload)
    first = process_mode_command(tmp_path)
    second = process_mode_command(tmp_path)
    assert second == first


def test_auto_off_blocks_temporary_escalation(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "set_auto", "enabled": False})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "begin_temporary", "requested_mode": "MAINTENANCE", "reason": "backup"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.USER
    assert any("automatic_switching_disabled" in item for item in state.drift)


def test_wrong_transition_token_cannot_end_another_task(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "begin_temporary", "requested_mode": "DEVELOPMENT", "reason": "build"})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "end_temporary", "transition_id": "wrong"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.active_transition_id == "req-1"
