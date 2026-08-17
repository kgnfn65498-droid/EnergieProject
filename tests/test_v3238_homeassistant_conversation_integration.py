from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CC = ROOT / "custom_components" / "energie_assistant"


def test_manifest_and_hacs_contract():
    manifest = json.loads((CC / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "energie_assistant"
    assert manifest["version"] == "32.3.8"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "service"
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] == "Energie Assistant"


def test_conversation_entity_is_explicitly_information_only():
    source = (CC / "conversation.py").read_text(encoding="utf-8")
    assert "ConversationEntityFeature(0)" in source
    assert "ConversationEntityFeature.CONTROL" not in source
    assert "_async_handle_message" in source
    assert "async_set_agent" in source


def test_privacy_switch_defaults_off_and_restores_state():
    source = (CC / "switch.py").read_text(encoding="utf-8")
    assert "RestoreEntity" in source
    assert "self._is_on = False" in source
    assert "async_get_last_state" in source
    conversation = (CC / "conversation.py").read_text(encoding="utf-8")
    assert "privacy_enabled" in conversation
    assert "privacy_disabled" in conversation


def test_hassio_discovery_and_manual_fallback_are_supported():
    source = (CC / "config_flow.py").read_text(encoding="utf-8")
    assert "async_step_hassio" in source
    assert "HassioServiceInfo" in source
    assert "async_step_user" in source
    assert '"host"' in source and '"port"' in source


def test_client_only_calls_discovered_read_only_response_endpoint():
    source = (CC / "client.py").read_text(encoding="utf-8")
    assert "/api/assistant/respond" in source
    assert '"query"' in source
    assert '"session_id"' in source
    assert "/api/services/" not in source
    assert "CONTROL" not in source
