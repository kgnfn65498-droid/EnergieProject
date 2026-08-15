import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
VERSIE = ROOT / "VERSIE.txt"
CHANGELOG = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG = ROOT / "slimmemeterportal_import/CHANGELOG.md"


def test_current_release_identity_is_synchronized():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    versie = VERSIE.read_text(encoding="utf-8").strip()
    assert versie == "32.2.2"
    assert 'version: "32.2.2"' in config
    assert 'APP_VERSION = "32.2.2"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main


def test_v32035_smp_report_fallback_contract_is_preserved():
    main = MAIN.read_text(encoding="utf-8")
    assert "def load_smp_month_metrics(" in main
    assert '"slimmemeterportal_fallback"' in main
    assert "def publish_durable_report_package(" in main
    assert '"02_Output" / "Rapportages"' in main
    assert "def rebuild_historical_report(" in main
    assert 'action="rebuild-historical-report"' in main


def test_current_changelog_preserves_smp_report_fallback_history():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert changelog.startswith("## v32.2.2 — Knowledge Base")
    assert "## v32.0.35 — Pagina 2 onbekende terugleververgoeding" in changelog
    assert "feed_in_compensation" in changelog
    assert "€0" in changelog
    assert "finalize_month" in changelog


def test_current_addon_changelog_is_current_release_only():
    changelog = ADDON_CHANGELOG.read_text(encoding="utf-8")
    assert "## 32.2.2 - Knowledge Base cleanup/idempotentieherstel" in changelog
    assert changelog.count("\n## ") == 1
    assert "\n## 32.0.33" not in changelog
