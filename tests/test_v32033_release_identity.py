import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
VERSIE = ROOT / "VERSIE.txt"
CHANGELOG = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG = ROOT / "slimmemeterportal_import/CHANGELOG.md"


def test_v32033_release_identity_is_synchronized():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    versie = VERSIE.read_text(encoding="utf-8").strip()
    assert versie == "32.0.33"
    assert 'version: "32.0.33"' in config
    assert 'APP_VERSION = "32.0.33"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main


def test_v32033_july_ingress_fallback_contract_is_present():
    main = MAIN.read_text(encoding="utf-8")
    assert 'ingress_root = destination_month / "HomeAssistant"' in main
    assert 'ingress_root.mkdir(parents=True, exist_ok=True)' in main
    assert 'HA-ingress ontbreekt voor' not in main
    assert 'destination_root = ingress_root / "SlimmeMeterPortal"' in main


def test_v32033_changelog_mentions_july_ingress_fallback():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert changelog.startswith("## v32.0.33 — Juli ingress/fallback")
    assert "HomeAssistant" in changelog
    assert "SlimmeMeterPortal" in changelog
    assert "finalize_month" in changelog


def test_v32033_addon_changelog_is_current_release_only():
    changelog = ADDON_CHANGELOG.read_text(encoding="utf-8")
    assert "## 32.0.33 - Juli ingress/fallback" in changelog
    assert changelog.count("\n## ") == 1
    assert "\n## 32.0.32" not in changelog
