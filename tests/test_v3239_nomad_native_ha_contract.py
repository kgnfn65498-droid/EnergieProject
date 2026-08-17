from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"
MAIN = ROOT / "slimmemeterportal_import" / "rootfs" / "app" / "main.py"
AUTOMATION = ROOT / "00_Config" / "HomeAssistant" / "Nomad_automation.yaml"


def test_no_hacs_or_custom_component_is_shipped():
    assert not (ROOT / "hacs.json").exists()
    assert not (ROOT / "custom_components" / "energie_assistant").exists()


def test_only_homeassistant_api_permission_remains_for_nomad_bridge():
    source = CONFIG.read_text(encoding="utf-8")
    assert "homeassistant_api: true" in source
    assert "hassio_api:" not in source
    assert "hassio_role:" not in source
    assert "discovery:" not in source
    assert "full_access: true" not in source
    assert "docker_api: true" not in source
    assert "8099/tcp" not in source


def test_nomad_options_are_configurable_and_safe_defaults():
    source = CONFIG.read_text(encoding="utf-8")
    assert 'assistant_event_bridge_enabled: true' in source
    assert 'assistant_display_name: "Nomad"' in source
    assert 'assistant_greeting_enabled: true' in source
    assert 'assistant_greeting_idle_seconds: 900' in source
    assert 'assistant_event_bridge_enabled: bool' in source
    assert 'assistant_display_name: str' in source
    assert 'assistant_greeting_enabled: bool' in source
    assert 'assistant_greeting_idle_seconds: "int(60,86400)"' in source


def test_native_nomad_automation_is_sentence_event_response_only():
    source = AUTOMATION.read_text(encoding="utf-8")
    assert 'trigger: conversation' in source
    assert 'Nomad {vraag}' in source
    assert 'No mad {vraag}' in source
    assert 'energie_nomad_request' in source
    assert 'energie_nomad_response' in source
    assert 'request_id:' in source
    assert 'query: "{{ trigger.slots.vraag }}"' in source
    assert 'wait_for_trigger:' in source
    assert 'timeout: "00:00:05"' in source
    assert 'set_conversation_response:' in source
    assert 'Nomad is tijdelijk niet beschikbaar.' in source
    assert 'mode: parallel' in source
    assert 'max: 5' in source
    forbidden = ["light.turn_", "switch.turn_", "climate.", "cover.", "lock.", "homeassistant.restart", "finalize_month"]
    for token in forbidden:
        assert token not in source


def test_automation_entity_is_documented_as_privacy_control():
    source = AUTOMATION.read_text(encoding="utf-8")
    assert "privacy" in source.lower()
    assert "automation" in source.lower()
    assert "energiedata" in source.lower()


def test_main_no_longer_imports_or_publishes_supervisor_discovery():
    source = MAIN.read_text(encoding="utf-8")
    assert "publish_assistant_discovery" not in source
    assert "assistant_discovery" not in source
    assert "HomeAssistantNomadBridge" in source


def test_nomad_request_id_uses_official_automation_this_context():
    source = AUTOMATION.read_text(encoding="utf-8")
    assert 'nomad_request_id: "{{ this.context.id }}"' in source
    assert 'nomad_request_id: "{{ context.id }}"' not in source
