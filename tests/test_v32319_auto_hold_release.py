import pathlib
import sys
from dataclasses import replace
from threading import Event
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from operating_modes import Mode, ModeState, save_mode_state
from release_validation_hold import activate_release_hold, load_release_hold
import operating_mode_auto_release as auto_release


def _development_state():
    return replace(
        ModeState.initial(),
        base_mode=Mode.DEVELOPMENT,
        effective_mode=Mode.DEVELOPMENT,
        development_session_active=True,
    )


def _healthy_app():
    return SimpleNamespace(
        APP_VERSION="32.3.19",
        Handler=object,
        html_page=lambda *args, **kwargs: "ok",
        STOP=Event(),
        operating_runtime_probe=lambda: {
            "workflow_running": False,
            "workflow_active": {},
            "cancel_requested": False,
            "run_on_start_effective": False,
            "schedule_effective": False,
            "full_workflow_effective": False,
            "automatic_month_close_effective": False,
            "release_processing": [],
        },
        append_audit_event=lambda *args, **kwargs: None,
    )


def test_automatic_release_uses_normal_validation_and_releases_only_when_green(tmp_path):
    save_mode_state(tmp_path, _development_state())
    activate_release_hold(tmp_path, "32.3.19", "release_install")
    app = _healthy_app()

    result = auto_release.automatic_release_hold_once(app, tmp_path, "32.3.19")
    hold = load_release_hold(tmp_path, "32.3.19")

    assert result["status"] == "released"
    assert result["validation"]["status"] == "ok"
    assert hold.active is False
    assert hold.emergency_release is False
    assert hold.released_by == "projectmanager_auto"


def test_automatic_release_keeps_hold_active_when_any_validation_check_is_blocked(tmp_path):
    save_mode_state(tmp_path, _development_state())
    activate_release_hold(tmp_path, "32.3.19", "release_install")
    app = _healthy_app()
    app.operating_runtime_probe = lambda: {
        "workflow_running": False,
        "workflow_active": {},
        "cancel_requested": False,
        "run_on_start_effective": False,
        "schedule_effective": True,
        "full_workflow_effective": False,
        "automatic_month_close_effective": False,
        "release_processing": [],
    }

    result = auto_release.automatic_release_hold_once(app, tmp_path, "32.3.19")
    hold = load_release_hold(tmp_path, "32.3.19")

    assert result["status"] == "blocked"
    assert hold.active is True
    assert hold.validation_status == "blocked"
    assert hold.emergency_release is False


def test_auto_release_worker_has_bounded_retry_schedule(monkeypatch, tmp_path):
    calls = []

    def always_blocked(app, root, version):
        calls.append((root, version))
        return {"status": "blocked"}

    monkeypatch.setattr(auto_release, "automatic_release_hold_once", always_blocked)

    class FakeStop:
        def __init__(self):
            self.waits = []

        def wait(self, seconds):
            self.waits.append(seconds)
            return False

    stop = FakeStop()
    result = auto_release.automatic_release_hold_worker(
        stop,
        object(),
        tmp_path,
        "32.3.19",
        retry_delays=(0.1, 0.2, 0.3),
    )

    assert result["status"] == "blocked"
    assert stop.waits == [0.1, 0.2, 0.3]
    assert len(calls) == 3


def test_auto_release_module_never_uses_emergency_release():
    text = (APP_ROOT / "operating_mode_auto_release.py").read_text(encoding="utf-8")
    assert "attempt_emergency_release_hold" not in text
    assert "emergency=True" not in text


def test_mode_entrypoint_starts_auto_release_worker_after_safety_layers():
    text = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert "automatic_release_hold_worker" in text
    assert text.index("install_release_hold_guards(app, root)") < text.index("target=automatic_release_hold_worker")
    assert text.index("install_mode_web(app, root)") < text.index("target=automatic_release_hold_worker")
