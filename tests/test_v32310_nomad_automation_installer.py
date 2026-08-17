from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
AUTOMATION = ROOT / "00_Config" / "HomeAssistant" / "Nomad_automation.yaml"
MAIN = APP / "main.py"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"


def _load_installer():
    path = APP / "ha_nomad_automation.py"
    spec = importlib.util.spec_from_file_location("ha_nomad_automation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_nomad_automation_template_omits_gui_managed_id():
    source = AUTOMATION.read_text(encoding="utf-8")
    assert "alias: Nomad - Energie Assistent" in source
    assert "\nid:" not in source
    assert 'Nomad {vraag}' in source
    assert 'No mad {vraag}' in source


def test_install_payload_has_no_id_and_only_nomad_event_bridge_behavior():
    mod = _load_installer()
    config = mod.build_nomad_automation_config()
    assert "id" not in config
    assert config["alias"] == "Nomad - Energie Assistent"
    assert config["triggers"][0]["trigger"] == "conversation"
    assert config["triggers"][0]["command"] == ["Nomad {vraag}", "No mad {vraag}"]
    assert config["mode"] == "parallel"
    assert config["max"] == 5
    serialized = json.dumps(config, ensure_ascii=False)
    assert "energie_nomad_request" in serialized
    assert "energie_nomad_response" in serialized
    assert "set_conversation_response" in serialized
    for forbidden in (
        "light.turn_",
        "switch.turn_",
        "climate.",
        "cover.",
        "lock.",
        "homeassistant.restart",
        "finalize_month",
    ):
        assert forbidden not in serialized


def test_installer_creates_missing_automation_via_narrow_supervisor_core_post(monkeypatch):
    mod = _load_installer()
    calls = []

    class Response:
        def __init__(self, status: int, body: dict):
            self.status = status
            self._raw = json.dumps(body).encode()
        def read(self):
            return self._raw
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, request.get_method(), dict(request.header_items()), request.data, timeout))
        if request.get_method() == "GET":
            raise HTTPError(request.full_url, 404, "not found", hdrs=None, fp=None)
        return Response(200, {"result": "ok"})

    monkeypatch.setenv("SUPERVISOR_TOKEN", "runtime-token")
    result = mod.ensure_nomad_automation(urlopen=fake_urlopen)
    assert result["status"] == "installed"
    assert result["automation_id"] == "nomad_energie_assistent"
    assert len(calls) == 3
    assert calls[0][0].endswith("/core/api/config/automation/config/nomad_energie_assistent")
    assert calls[0][1] == "GET"
    assert calls[1][1] == "POST"
    assert calls[2][0].endswith("/core/api/services/automation/reload")
    assert calls[2][1] == "POST"
    assert json.loads(calls[2][3].decode()) == {}
    headers = {k.lower(): v for k, v in calls[1][2].items()}
    assert headers["authorization"] == "Bearer runtime-token"
    body = json.loads(calls[1][3].decode())
    assert "id" not in body
    assert body["alias"] == "Nomad - Energie Assistent"
    assert "runtime-token" not in json.dumps(result)


def test_installer_does_not_overwrite_existing_automation(monkeypatch):
    mod = _load_installer()
    calls = []
    existing = mod.build_nomad_automation_config()

    class Response:
        status = 200
        def read(self):
            return json.dumps(existing).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        calls.append(request.get_method())
        return Response()

    monkeypatch.setenv("SUPERVISOR_TOKEN", "runtime-token")
    result = mod.ensure_nomad_automation(urlopen=fake_urlopen)
    assert result["status"] == "already_present"
    assert calls == ["GET", "POST"]


def test_installer_refuses_conflicting_automation_id(monkeypatch):
    mod = _load_installer()
    calls = []

    class Response:
        status = 200
        def read(self):
            return json.dumps({"alias": "Anders", "triggers": [], "actions": []}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=0):
        calls.append(request.get_method())
        return Response()

    monkeypatch.setenv("SUPERVISOR_TOKEN", "runtime-token")
    result = mod.ensure_nomad_automation(urlopen=fake_urlopen)
    assert result["status"] == "conflict"
    assert calls == ["GET"]


def test_installer_requires_runtime_supervisor_token(monkeypatch):
    mod = _load_installer()
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="SUPERVISOR_TOKEN"):
        mod.ensure_nomad_automation(urlopen=lambda *_args, **_kwargs: None)


def test_main_records_automatic_nomad_automation_installation_without_new_permissions():
    main = MAIN.read_text(encoding="utf-8")
    addon = CONFIG.read_text(encoding="utf-8")
    assert "ensure_nomad_automation" in main
    assert 'result["nomad_automation_installation"]' in main
    assert "homeassistant_api: true" in addon
    assert "hassio_api:" not in addon
    assert "hassio_role:" not in addon
    assert "full_access: true" not in addon
    assert "docker_api: true" not in addon
