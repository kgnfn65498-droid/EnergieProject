from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"


def _load():
    path = APP / "assistant_discovery.py"
    spec = importlib.util.spec_from_file_location("assistant_discovery", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_discovery_payload_is_internal_and_secret_free():
    mod = _load()
    payload = mod.build_discovery_payload(host="172.30.1.55", app_version="32.3.8")
    assert payload["service"] == "energie_assistant"
    assert payload["config"] == {
        "host": "172.30.1.55",
        "port": 8099,
        "ssl": False,
        "api_path": "/api/assistant/respond",
        "version": "32.3.8",
    }
    assert "token" not in json.dumps(payload).lower()


def test_addon_declares_discovery_without_external_port_mapping():
    source = CONFIG.read_text(encoding="utf-8")
    assert "discovery:" in source
    assert "- energie_assistant" in source
    assert '8099/tcp' not in source


def test_discovery_module_uses_supervisor_self_info_and_replaces_uuid():
    source = (APP / "assistant_discovery.py").read_text(encoding="utf-8")
    assert "http://supervisor/addons/self/info" in source
    assert "http://supervisor/discovery" in source
    assert "DELETE" in source
    assert "energie_assistant_discovery.json" in source


def test_supervisor_discovery_permission_is_narrow_default_role_only():
    source = CONFIG.read_text(encoding="utf-8")
    assert "hassio_api: true" in source
    assert "hassio_role: default" in source
    assert "hassio_role: manager" not in source
    assert "hassio_role: admin" not in source
    assert "full_access: true" not in source
    assert "docker_api: true" not in source


def test_discovery_replaces_previous_uuid_and_persists_uuid_only(tmp_path):
    mod = _load()
    state = tmp_path / "energie_assistant_discovery.json"
    state.write_text('{"uuid":"old-uuid"}\n', encoding="utf-8")
    mod.DISCOVERY_STATE_PATH = state
    calls = []

    def fake_request(url, *, method="GET", payload=None, timeout=5.0):
        calls.append((url, method, payload))
        if url == mod.SUPERVISOR_SELF_INFO_URL:
            return {"data": {"ip_address": "172.30.1.55"}}
        if method == "DELETE":
            return {}
        if url == mod.SUPERVISOR_DISCOVERY_URL and method == "POST":
            return {"data": {"uuid": "new-uuid"}}
        raise AssertionError((url, method, payload))

    mod._request_json = fake_request
    result = mod.publish_assistant_discovery(app_version="32.3.8")
    assert result["uuid"] == "new-uuid"
    assert (f"{mod.SUPERVISOR_DISCOVERY_URL}/old-uuid", "DELETE", None) in calls
    assert json.loads(state.read_text(encoding="utf-8")) == {"uuid": "new-uuid"}
