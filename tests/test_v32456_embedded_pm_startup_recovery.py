import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for value in (str(APP), str(PM)):
    if value not in sys.path:
        sys.path.insert(0, value)


def _runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "Inbox/projectmanager_v2/RuntimeV2"
    runtime.mkdir(parents=True)
    return runtime


def _write_status(runtime: Path, *, release: str, updated_epoch: float):
    path = runtime / "status/current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "release": {"version": release},
        "updated_at": datetime.fromtimestamp(updated_epoch, timezone.utc).isoformat(),
    }), encoding="utf-8")


def test_startup_recovery_accepts_only_fresh_current_release_status(tmp_path):
    from startup_recovery import startup_recovery_check

    runtime = _runtime(tmp_path)
    startup = 1000.0
    _write_status(runtime, release="32.4.56", updated_epoch=1005.0)

    calls = []
    result = startup_recovery_check(
        tmp_path,
        expected_version="32.4.56",
        startup_epoch=startup,
        now_epoch=1010.0,
        stale_after_seconds=900,
        request_restart=lambda: calls.append("restart") or True,
    )

    assert result["status"] == "GREEN"
    assert result["reason"] == "fresh_pm_cycle_after_startup"
    assert calls == []


def test_startup_recovery_requests_exactly_one_self_restart_after_stale_first_cycle(tmp_path):
    from startup_recovery import startup_recovery_check

    runtime = _runtime(tmp_path)
    _write_status(runtime, release="32.4.55", updated_epoch=900.0)
    cycle = runtime / "embedded_runtime/cycle.json"
    cycle.parent.mkdir(parents=True)
    cycle.write_text(json.dumps({
        "status": "RUNNING",
        "release_version": "32.4.56",
        "started_at_epoch": 1001.0,
    }), encoding="utf-8")

    calls = []
    result = startup_recovery_check(
        tmp_path,
        expected_version="32.4.56",
        startup_epoch=1000.0,
        now_epoch=2000.0,
        stale_after_seconds=900,
        restart_window_seconds=3600,
        max_restart_requests=1,
        request_restart=lambda: calls.append("restart") or True,
    )

    assert result["status"] == "RESTART_REQUESTED"
    assert result["reason"] == "pm_first_cycle_stale"
    assert calls == ["restart"]
    persisted = json.loads((runtime / "embedded_startup/recovery.json").read_text(encoding="utf-8"))
    assert persisted["restart_requests"] == 1
    assert persisted["delete_performed"] is False


def test_startup_recovery_second_stale_boot_fails_closed_without_restart_loop(tmp_path):
    from startup_recovery import startup_recovery_check

    runtime = _runtime(tmp_path)
    state = runtime / "embedded_startup/recovery.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({
        "schema": "energie_embedded_pm_startup_recovery_v1",
        "window_started_at_epoch": 1500.0,
        "restart_requests": 1,
        "status": "RESTART_REQUESTED",
        "delete_performed": False,
    }), encoding="utf-8")

    calls = []
    result = startup_recovery_check(
        tmp_path,
        expected_version="32.4.56",
        startup_epoch=2000.0,
        now_epoch=3000.0,
        stale_after_seconds=900,
        restart_window_seconds=3600,
        max_restart_requests=1,
        request_restart=lambda: calls.append("restart") or True,
    )

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "restart_budget_exhausted"
    assert calls == []
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["restart_requests"] == 1


def test_supervisor_self_restart_uses_bearer_token_and_self_endpoint(monkeypatch):
    import startup_recovery as mod

    seen = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["authorization"] = request.headers.get("Authorization")
        seen["method"] = request.get_method()
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    assert mod.request_supervisor_self_restart("secret-token") is True
    assert seen["url"] == "http://supervisor/addons/self/restart"
    assert seen["authorization"] == "Bearer secret-token"
    assert seen["method"] == "POST"
    assert seen["timeout"] <= 10


def test_embedded_runtime_writes_running_then_green_cycle_evidence(tmp_path, monkeypatch):
    import embedded_runtime as embedded

    runtime_root = _runtime(tmp_path)
    events = []

    class Config:
        system_root = str(runtime_root)
        running_release_version = "32.4.56"

    class Runtime:
        config = Config()
        def run_once(self):
            events.append("run_once")
            return {
                "cycle_generation": "g1",
                "provenance": {"generation": "g1", "phase": "FINAL"},
            }

    class Stop:
        def __init__(self):
            self.waits = 0
        def is_set(self):
            return False
        def wait(self, delay):
            self.waits += 1
            return True

    original = embedded.atomic_write_json

    def capture(path, payload, **kwargs):
        if str(path).endswith("embedded_runtime/cycle.json"):
            events.append(payload["status"])
        return original(path, payload, **kwargs)

    monkeypatch.setattr(embedded, "atomic_write_json", capture)
    result = embedded.run_embedded(Stop(), runtime=Runtime(), interval_seconds=60)

    assert result["state"] == "stopped"
    assert events.index("RUNNING") < events.index("run_once") < events.index("GREEN")
    payload = json.loads((runtime_root / "embedded_runtime/cycle.json").read_text(encoding="utf-8"))
    assert payload["status"] == "GREEN"
    assert payload["release_version"] == "32.4.56"


def test_mode_entrypoint_starts_bounded_pm_startup_recovery_monitor():
    source = (ROOT / "tests/fixtures/pre57/mode_entrypoint.py").read_text(encoding="utf-8")
    assert "startup_recovery_daemon" in source
    assert "pm-startup-recovery" in source
    assert "SUPERVISOR_TOKEN" in source
