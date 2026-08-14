import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
VERSIE = ROOT / "VERSIE.txt"
CHANGELOG = ROOT / "CHANGELOG.md"
STATIC = ROOT / "tests/test_static.py"


def test_v32029_release_identity_is_synchronized():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    versie = VERSIE.read_text(encoding="utf-8").strip()

    assert versie == "32.0.29"
    assert 'version: "32.0.29"' in config
    assert 'APP_VERSION = "32.0.29"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main


def test_v32029_static_release_expectations_are_synchronized():
    static = STATIC.read_text(encoding="utf-8")
    assert '"32.0.28"' not in static
    assert 'v32.0.28: OK' not in static
    assert 'v32.0.28: FOUT' not in static
    assert '"32.0.29"' in static


def test_v32029_runtime_identity_has_no_old_processed_retention_label():
    main = MAIN.read_text(encoding="utf-8")
    assert "HA-app processed-retentie v32.0.28" not in main
    assert "HA-app processed-retentie v32.0.29" in main


def test_v32029_changelog_has_crash_recovery_export_entry():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert changelog.startswith("## v32.0.29 — Crash Recovery browser/iCloud export")
    assert "Energie_Complete_Backup_*.zip" in changelog
    assert "FULL_RECOVERY*.tar.gz" in changelog
    assert "RestoreStaging" in changelog
    assert "finalize_month" in changelog
