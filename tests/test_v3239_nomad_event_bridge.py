from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"


def _load_bridge():
    path = APP / "assistant_event_bridge.py"
    spec = importlib.util.spec_from_file_location("assistant_event_bridge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_response():
    path = APP / "assistant_response.py"
    spec = importlib.util.spec_from_file_location("assistant_response", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_nomad_event_protocol_constants_are_narrow_and_internal():
    mod = _load_bridge()
    assert mod.CORE_WEBSOCKET_URL == "ws://supervisor/core/websocket"
    assert mod.REQUEST_EVENT == "energie_nomad_request"
    assert mod.RESPONSE_EVENT == "energie_nomad_response"
    assert mod.MAX_QUERY_BYTES == 32 * 1024


def test_request_validation_rejects_unknown_empty_and_oversized_payloads():
    mod = _load_bridge()
    valid = mod.validate_request_event({"request_id": "abc-123", "query": "Hoeveel gas?", "session_id": "living-room"})
    assert valid == {"request_id": "abc-123", "query": "Hoeveel gas?", "session_id": "living-room"}

    with pytest.raises(ValueError, match="unsupported"):
        mod.validate_request_event({"request_id": "x", "query": "gas", "write": True})
    with pytest.raises(ValueError, match="query"):
        mod.validate_request_event({"request_id": "x", "query": "   "})
    with pytest.raises(ValueError, match="32 KiB"):
        mod.validate_request_event({"request_id": "x", "query": "x" * (32 * 1024 + 1)})
    with pytest.raises(ValueError, match="request_id"):
        mod.validate_request_event({"request_id": "", "query": "gas"})


def test_greeting_tracker_greets_first_request_and_after_idle_only():
    mod = _load_bridge()
    tracker = mod.NomadGreetingTracker(idle_seconds=900)
    assert tracker.should_greet("living-room", now=1000.0) is True
    assert tracker.should_greet("living-room", now=1100.0) is False
    assert tracker.should_greet("living-room", now=1999.9) is False
    assert tracker.should_greet("living-room", now=2899.9) is True
    assert tracker.should_greet("phone", now=2900.0) is True


def test_event_request_uses_existing_assistant_response_and_correlates_id():
    mod = _load_bridge()
    calls = []

    def respond(query, session_id=None):
        calls.append((query, session_id))
        return {"speech": "In augustus heb je 4,679 m³ gas gebruikt.", "session_id": session_id, "version": "32.3.9"}

    tracker = mod.NomadGreetingTracker(idle_seconds=900)
    response = mod.handle_request_event(
        {"request_id": "r1", "query": "Hoeveel gas?", "session_id": "living-room"},
        respond=respond,
        display_name="Nomad",
        greeting_enabled=True,
        greeting_tracker=tracker,
        app_version="32.3.9",
        now=10.0,
    )
    assert calls == [("Hoeveel gas?", "living-room")]
    assert response == {
        "request_id": "r1",
        "status": "ok",
        "version": "32.3.9",
        "speech": "Nomad hier. In augustus heb je 4,679 m³ gas gebruikt.",
        "session_id": "living-room",
        "greeted": True,
    }


def test_websocket_auth_subscribe_and_fire_event_protocol_never_persists_token():
    mod = _load_bridge()

    class FakeSocket:
        def __init__(self):
            self.receives = iter([
                json.dumps({"type": "auth_required", "ha_version": "2026.8.2"}),
                json.dumps({"type": "auth_ok", "ha_version": "2026.8.2"}),
                json.dumps({"id": 1, "type": "result", "success": True, "result": None}),
            ])
            self.sent = []

        def recv(self):
            return next(self.receives)

        def send(self, value):
            self.sent.append(json.loads(value))

    ws = FakeSocket()
    mod.authenticate_and_subscribe(ws, "secret-token")
    assert ws.sent[0] == {"type": "auth", "access_token": "secret-token"}
    assert ws.sent[1] == {"id": 1, "type": "subscribe_events", "event_type": "energie_nomad_request"}

    next_id = mod.fire_response_event(ws, 2, {"request_id": "r1", "speech": "Nomad hier."})
    assert next_id == 3
    assert ws.sent[2] == {
        "id": 2,
        "type": "fire_event",
        "event_type": "energie_nomad_response",
        "event_data": {"request_id": "r1", "speech": "Nomad hier."},
    }

    source = (APP / "assistant_event_bridge.py").read_text(encoding="utf-8")
    assert "DISCOVERY" not in source
    assert "write_text" not in source
    assert "SUPERVISOR_TOKEN" in source


def test_shared_response_builder_is_used_by_http_and_bridge():
    mod = _load_response()

    class Engine:
        def context(self, query, session_id=None):
            return {
                "session_id": session_id or "new-session",
                "resolved": {"month": "2026_08", "domains": ["gas"]},
                "quality": {"status": "PARTIAL"},
                "evidence": {"metrics": {"gas_m3": 4.679}},
            }

    payload = mod.build_assistant_response_payload(Engine(), "32.3.9", "Hoeveel gas?", "session-1")
    assert payload["schema"] == "energie_assistant_response_v1"
    assert payload["version"] == "32.3.9"
    assert payload["session_id"] == "session-1"
    assert "4,679" in payload["speech"]
    assert payload["context"]["quality"]["status"] == "PARTIAL"

    main_source = (APP / "main.py").read_text(encoding="utf-8")
    assert "build_assistant_response_payload" in main_source


def test_bridge_serves_one_home_assistant_request_over_fake_websocket(monkeypatch):
    mod = _load_bridge()

    class Stop:
        def __init__(self):
            self.value = False
        def is_set(self):
            return self.value
        def set(self):
            self.value = True
        def wait(self, seconds):
            self.value = True
            return True

    stop = Stop()

    class FakeSocket:
        def __init__(self):
            self.receives = iter([
                json.dumps({"type": "auth_required", "ha_version": "2026.8.2"}),
                json.dumps({"type": "auth_ok", "ha_version": "2026.8.2"}),
                json.dumps({"id": 1, "type": "result", "success": True, "result": None}),
                json.dumps({
                    "id": 1,
                    "type": "event",
                    "event": {
                        "event_type": "energie_nomad_request",
                        "data": {"request_id": "req-42", "query": "Hoeveel gas?", "session_id": "woonkamer"},
                    },
                }),
            ])
            self.sent = []
        def recv(self):
            return next(self.receives)
        def send(self, value):
            parsed = json.loads(value)
            self.sent.append(parsed)
            if parsed.get("type") == "fire_event":
                stop.set()
        def close(self):
            pass

    monkeypatch.setenv("SUPERVISOR_TOKEN", "runtime-secret")
    ws = FakeSocket()
    bridge = mod.HomeAssistantNomadBridge(
        stop,
        respond=lambda query, session_id=None: {
            "speech": "Je gasverbruik is 4,679 m³.",
            "session_id": session_id,
        },
        app_version="32.3.9",
        display_name="Nomad",
        greeting_enabled=True,
    )
    bridge._serve(ws)
    response = ws.sent[-1]
    assert response["type"] == "fire_event"
    assert response["event_type"] == "energie_nomad_response"
    assert response["event_data"]["request_id"] == "req-42"
    assert response["event_data"]["speech"].startswith("Nomad hier.")
    status = bridge.status_snapshot()
    assert status["connected"] is True
    assert "runtime-secret" not in json.dumps(status)
    assert "Hoeveel gas?" not in json.dumps(status)
