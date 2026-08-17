from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOMATION = ROOT / "00_Config" / "HomeAssistant" / "Nomad_automation.yaml"


def test_v3238_custom_component_hacs_route_is_superseded_and_removed():
    assert not (ROOT / "hacs.json").exists()
    assert not (ROOT / "custom_components" / "energie_assistant").exists()


def test_native_home_assistant_automation_remains_information_only():
    source = AUTOMATION.read_text(encoding="utf-8")
    assert "trigger: conversation" in source
    assert "energie_nomad_request" in source
    assert "energie_nomad_response" in source
    assert "set_conversation_response" in source
    assert "CONTROL" not in source
    for token in ("light.turn_", "switch.turn_", "climate.", "cover.", "lock."):
        assert token not in source


def test_privacy_is_native_automation_toggle_not_custom_switch():
    source = AUTOMATION.read_text(encoding="utf-8").lower()
    assert "privacy" in source
    assert "automation" in source
    assert "energiedata" in source
