from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import" / "rootfs" / "app" / "main.py"


def load_main():
    name = "main_v32422_closed_month_startup_gate"
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def automatic_options():
    return SimpleNamespace(
        automatic_month_close_enabled=True,
        automatic_month_close_day=1,
        automatic_month_close_hour=0,
        automatic_month_close_retry_hours=6,
        homeassistant_energy_sampling_enabled=False,
        run_on_start=False,
        schedule_enabled=False,
    )


def test_due_never_returns_month_already_closed_by_recovery_manager(monkeypatch):
    m = load_main()
    options = automatic_options()
    monkeypatch.setattr(m, "automatic_production_readiness", lambda: {"ready": True})
    monkeypatch.setattr(m, "automatic_month_is_completed", lambda _month: False)
    monkeypatch.setattr(m, "load_state", lambda: {})
    monkeypatch.setattr(
        m,
        "recovery_month_closure_proof",
        lambda month: {
            "closed": month == "2026_08",
            "evidence": "RecoveryManager MonthClosure_2026_08=CLOSED",
        },
    )

    assert m.automatic_month_close_due(
        options,
        datetime(2026, 9, 9, 13, 0, tzinfo=m.TZ),
    ) is None


def test_due_still_returns_previous_month_when_recovery_manager_does_not_prove_closed(monkeypatch):
    m = load_main()
    options = automatic_options()
    monkeypatch.setattr(m, "automatic_production_readiness", lambda: {"ready": True})
    monkeypatch.setattr(m, "automatic_month_is_completed", lambda _month: False)
    monkeypatch.setattr(m, "load_state", lambda: {})
    monkeypatch.setattr(
        m,
        "recovery_month_closure_proof",
        lambda _month: {"closed": False, "evidence": None},
    )

    assert m.automatic_month_close_due(
        options,
        datetime(2026, 9, 9, 13, 0, tzinfo=m.TZ),
    ) == "2026_08"


class OneLoopStop:
    def __init__(self):
        self._checks = 0

    def is_set(self):
        self._checks += 1
        return self._checks > 1

    def wait(self, _seconds):
        return None


class Gate:
    def __init__(self, ready: bool):
        self.ready = ready

    def is_set(self):
        return self.ready


def test_scheduler_does_not_evaluate_automatic_close_before_startup_recovery_gate(monkeypatch):
    m = load_main()
    calls = []
    monkeypatch.setattr(m, "STOP", OneLoopStop())
    monkeypatch.setattr(m, "STARTUP_RECOVERY_READY", Gate(False), raising=False)
    monkeypatch.setattr(m.Options, "load", classmethod(lambda cls: automatic_options()))
    monkeypatch.setattr(m, "effective_homewizard_devices", lambda _options: [])
    monkeypatch.setattr(m, "automatic_month_close_due", lambda *_args: calls.append("due") or None)
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)

    m.scheduler()

    assert calls == []


def test_scheduler_evaluates_automatic_close_after_startup_recovery_gate(monkeypatch):
    m = load_main()
    calls = []
    monkeypatch.setattr(m, "STOP", OneLoopStop())
    monkeypatch.setattr(m, "STARTUP_RECOVERY_READY", Gate(True), raising=False)
    monkeypatch.setattr(m.Options, "load", classmethod(lambda cls: automatic_options()))
    monkeypatch.setattr(m, "effective_homewizard_devices", lambda _options: [])
    monkeypatch.setattr(m, "automatic_month_close_due", lambda *_args: calls.append("due") or None)
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)

    m.scheduler()

    assert calls == ["due"]


def test_main_sets_startup_recovery_gate_only_after_recovery_controller_returns():
    source = MAIN.read_text(encoding="utf-8")
    startup = source[source.index("def startup_self_test()") : source.index("threading.Thread(target=startup_self_test", source.index("def startup_self_test()"))]
    assert "recovery_result = run_recovery_controller(trigger=\"startup\")" in startup
    assert "STARTUP_RECOVERY_READY.set()" in startup
    assert startup.index("recovery_result = run_recovery_controller") < startup.index("STARTUP_RECOVERY_READY.set()")
