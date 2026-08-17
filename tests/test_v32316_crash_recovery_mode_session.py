import json
import pathlib
import sys
from dataclasses import replace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, load_mode_state, save_mode_state
import operating_mode_crash_recovery as crash_mode


def _state_for(base: Mode) -> ModeState:
    return replace(
        ModeState.initial(),
        base_mode=base,
        effective_mode=base,
        development_session_active=base is Mode.DEVELOPMENT,
    )


@pytest.mark.parametrize("base", [Mode.USER, Mode.DEVELOPMENT])
def test_safe_backup_session_returns_exact_base_after_pass(tmp_path, base):
    save_mode_state(tmp_path, _state_for(base))

    session = crash_mode.begin_crash_recovery_mode_session(tmp_path)
    during = load_mode_state(tmp_path)

    assert session["original_base_mode"] == base.value
    assert during.base_mode is base
    assert during.effective_mode is Mode.MAINTENANCE
    assert during.active_transition_id == session["transition_id"]
    assert during.development_session_active is (base is Mode.DEVELOPMENT)

    crash_mode.finish_crash_recovery_mode_session(tmp_path, outcome="pass")
    final = load_mode_state(tmp_path)
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))

    assert final.base_mode is base
    assert final.effective_mode is base
    assert final.active_transition_id == ""
    assert final.development_session_active is (base is Mode.DEVELOPMENT)
    assert saved["phase"] == "completed"
    assert saved["outcome"] == "pass"


@pytest.mark.parametrize("base", [Mode.USER, Mode.DEVELOPMENT])
def test_safe_backup_failure_returns_exact_base_and_records_failed(tmp_path, base):
    save_mode_state(tmp_path, _state_for(base))
    crash_mode.begin_crash_recovery_mode_session(tmp_path)

    crash_mode.finish_crash_recovery_mode_session(
        tmp_path,
        outcome="failed_safe",
        reason="checksum mismatch",
    )

    final = load_mode_state(tmp_path)
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert final.base_mode is base
    assert final.effective_mode is base
    assert final.development_session_active is (base is Mode.DEVELOPMENT)
    assert saved["phase"] == "completed"
    assert saved["outcome"] == "failed_safe"
    assert saved["reason"] == "checksum mismatch"


def test_unsafe_partial_mutation_keeps_maintenance(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    session = crash_mode.begin_crash_recovery_mode_session(
        tmp_path,
        operation_class="mutating_maintenance",
    )

    crash_mode.finish_crash_recovery_mode_session(
        tmp_path,
        outcome="unsafe",
        reason="restore changed source before failure",
    )

    state = load_mode_state(tmp_path)
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.MAINTENANCE
    assert state.active_transition_id == session["transition_id"]
    assert state.development_session_active is True
    assert saved["phase"] == "unsafe_hold"
    assert saved["outcome"] == "unsafe"


def test_conflicting_temporary_transition_is_refused(tmp_path):
    state = replace(
        _state_for(Mode.DEVELOPMENT),
        effective_mode=Mode.MAINTENANCE,
        active_transition_id="other-transition",
        temporary_reason="other maintenance",
    )
    save_mode_state(tmp_path, state)

    with pytest.raises(RuntimeError, match="temporary transition"):
        crash_mode.begin_crash_recovery_mode_session(tmp_path)

    after = load_mode_state(tmp_path)
    assert after.active_transition_id == "other-transition"
    assert after.effective_mode is Mode.MAINTENANCE


def test_export_wrapper_keeps_one_maintenance_session_across_nested_calls(tmp_path):
    from types import SimpleNamespace

    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    observed = []
    app = SimpleNamespace()

    def raw_complete(*args, **kwargs):
        state = load_mode_state(tmp_path)
        observed.append(("complete", state.effective_mode, state.active_transition_id))
        return {"status": "verified", "deep_verified": True}

    def raw_stage(*args, **kwargs):
        state = load_mode_state(tmp_path)
        observed.append(("stage", state.effective_mode, state.active_transition_id))
        return {"status": "staged", "source_project_modified": False}

    def raw_export(*args, **kwargs):
        state = load_mode_state(tmp_path)
        observed.append(("export_start", state.effective_mode, state.active_transition_id))
        app.run_complete_crash_recovery()
        state = load_mode_state(tmp_path)
        observed.append(("after_complete", state.effective_mode, state.active_transition_id))
        app.run_complete_restore_staging()
        state = load_mode_state(tmp_path)
        observed.append(("after_stage", state.effective_mode, state.active_transition_id))
        return {"status": "ready_for_download", "source_project_modified": False}

    app.run_complete_crash_recovery = raw_complete
    app.run_complete_restore_staging = raw_stage
    app.run_complete_crash_recovery_export = raw_export

    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)
    result = app.run_complete_crash_recovery_export()

    assert result == {"status": "ready_for_download", "source_project_modified": False}
    assert observed
    assert all(mode is Mode.MAINTENANCE for _, mode, _ in observed)
    transition_ids = {transition_id for _, _, transition_id in observed}
    assert len(transition_ids) == 1
    assert "" not in transition_ids

    final = load_mode_state(tmp_path)
    assert final.base_mode is Mode.DEVELOPMENT
    assert final.effective_mode is Mode.DEVELOPMENT
    assert final.development_session_active is True
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["outcome"] == "pass"
    assert saved["phase"] == "completed"


@pytest.mark.parametrize("base", [Mode.USER, Mode.DEVELOPMENT])
def test_wrapper_safe_failure_returns_original_mode(tmp_path, base):
    from types import SimpleNamespace

    save_mode_state(tmp_path, _state_for(base))
    app = SimpleNamespace(
        run_complete_crash_recovery=lambda: {"status": "error", "error": "verify failed"},
        run_complete_restore_staging=lambda: {"status": "error", "error": "not used"},
        run_complete_crash_recovery_export=lambda: {"status": "error", "error": "export failed"},
    )
    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)

    result = app.run_complete_crash_recovery_export()

    assert result["status"] == "error"
    final = load_mode_state(tmp_path)
    assert final.base_mode is base
    assert final.effective_mode is base
    assert final.development_session_active is (base is Mode.DEVELOPMENT)
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["outcome"] == "failed_safe"
    assert saved["phase"] == "completed"


def test_wrapper_unsafe_source_mutation_keeps_maintenance(tmp_path):
    from types import SimpleNamespace

    save_mode_state(tmp_path, _state_for(Mode.USER))
    app = SimpleNamespace(
        run_complete_crash_recovery=lambda: {"status": "verified"},
        run_complete_restore_staging=lambda: {
            "status": "error",
            "error": "restore staging unsafe",
            "source_project_modified": True,
        },
        run_complete_crash_recovery_export=lambda: {"status": "ready_for_download"},
    )
    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)

    result = app.run_complete_restore_staging()

    assert result["source_project_modified"] is True
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.MAINTENANCE
    assert state.active_transition_id
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["outcome"] == "unsafe"
    assert saved["phase"] == "unsafe_hold"


def test_reboot_during_backup_verify_records_failed_safe_and_returns_base(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="backup_verify")

    recovery = crash_mode.recover_crash_recovery_mode_session(tmp_path)

    assert recovery["preserve_temporary"] is False
    assert recovery["outcome"] == "failed_safe"
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.development_session_active is True
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["phase"] == "completed"
    assert saved["outcome"] == "failed_safe"
    assert "restart" in saved["reason"]


def test_reboot_during_mutating_maintenance_keeps_maintenance(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.USER))
    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="mutating_maintenance")

    recovery = crash_mode.recover_crash_recovery_mode_session(tmp_path)

    assert recovery["preserve_temporary"] is True
    assert recovery["outcome"] == "unsafe"
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.MAINTENANCE
    assert state.active_transition_id
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["phase"] == "unsafe_hold"
    assert saved["outcome"] == "unsafe"


def test_mode_entrypoint_recovers_crash_session_before_generic_stale_transition():
    text = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert "recover_crash_recovery_mode_session" in text
    assert "install_crash_recovery_mode_integration" in text
    assert text.index("recover_crash_recovery_mode_session(root)") < text.index("recover_startup_mode_state(root)")
    assert text.index("install_crash_recovery_mode_integration(app, root)") < text.index("app.main()")


def test_new_crash_recovery_cannot_reuse_or_clear_unsafe_hold(tmp_path):
    save_mode_state(tmp_path, _state_for(Mode.USER))
    crash_mode.begin_crash_recovery_mode_session(tmp_path, operation_class="mutating_maintenance")
    crash_mode.finish_crash_recovery_mode_session(
        tmp_path,
        outcome="unsafe",
        reason="partial restore requires repair",
    )

    with pytest.raises(RuntimeError, match="already active|unsafe"):
        crash_mode.begin_crash_recovery_mode_session(tmp_path)

    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.MAINTENANCE
    saved = json.loads(crash_mode.crash_recovery_session_path(tmp_path).read_text(encoding="utf-8"))
    assert saved["phase"] == "unsafe_hold"
    assert saved["outcome"] == "unsafe"


def test_concurrent_request_is_not_treated_as_nested_call(tmp_path):
    import threading
    from types import SimpleNamespace

    save_mode_state(tmp_path, _state_for(Mode.DEVELOPMENT))
    app = SimpleNamespace()
    concurrent = {"raw_calls": 0, "error": None}

    def raw_complete(*args, **kwargs):
        concurrent["raw_calls"] += 1
        return {"status": "verified"}

    def raw_stage(*args, **kwargs):
        return {"status": "staged", "source_project_modified": False}

    def raw_export(*args, **kwargs):
        def concurrent_call():
            try:
                app.run_complete_crash_recovery()
            except Exception as exc:  # expected: independent request is refused
                concurrent["error"] = exc

        thread = threading.Thread(target=concurrent_call)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        return {"status": "ready_for_download", "source_project_modified": False}

    app.run_complete_crash_recovery = raw_complete
    app.run_complete_restore_staging = raw_stage
    app.run_complete_crash_recovery_export = raw_export
    crash_mode.install_crash_recovery_mode_integration(app, tmp_path)

    result = app.run_complete_crash_recovery_export()

    assert result["status"] == "ready_for_download"
    assert concurrent["raw_calls"] == 0
    assert isinstance(concurrent["error"], RuntimeError)
    assert "already active" in str(concurrent["error"])
    state = load_mode_state(tmp_path)
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.development_session_active is True
