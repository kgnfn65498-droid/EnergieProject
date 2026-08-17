from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"


def test_v3238_supervisor_discovery_is_superseded_by_native_event_bridge():
    source = CONFIG.read_text(encoding="utf-8")
    assert "homeassistant_api: true" in source
    assert "hassio_api:" not in source
    assert "hassio_role:" not in source
    assert "discovery:" not in source
    assert "8099/tcp" not in source


def test_legacy_assistant_discovery_module_is_not_active_or_shipped():
    assert not (APP / "assistant_discovery.py").exists()
    main = (APP / "main.py").read_text(encoding="utf-8")
    assert "assistant_discovery" not in main
    assert "publish_assistant_discovery" not in main
    assert "HomeAssistantNomadBridge" in main


def test_native_bridge_reduces_supervisor_permissions():
    source = CONFIG.read_text(encoding="utf-8")
    assert "full_access: true" not in source
    assert "docker_api: true" not in source
    assert "hassio_role: manager" not in source
    assert "hassio_role: admin" not in source
