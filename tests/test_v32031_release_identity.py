import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
VERSIE = ROOT / "VERSIE.txt"
CHANGELOG = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG = ROOT / "slimmemeterportal_import/CHANGELOG.md"


def test_v32031_release_identity_is_synchronized():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    versie = VERSIE.read_text(encoding="utf-8").strip()

    assert versie == "32.0.31"
    assert 'version: "32.0.31"' in config
    assert 'APP_VERSION = "32.0.31"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main


def test_v32031_crash_recovery_filename_contract_is_present():
    main = MAIN.read_text(encoding="utf-8")
    assert '%Y-%m-%d %H.%M CrashRecovery EnergieProject.zip' in main
    assert 'EnergieProject_Complete_Crash_Recovery_' not in main


def test_v32031_changelog_mentions_structural_live_snapshot_fix():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert changelog.startswith("## v32.0.31 — Crash Recovery live-snapshot")
    assert "watcher-heartbeats" in changelog
    assert "finalize_month" in changelog


def test_v32031_addon_changelog_is_current_release_only():
    changelog = ADDON_CHANGELOG.read_text(encoding="utf-8")
    assert "## 32.0.31 - Crash Recovery live-snapshot" in changelog
    assert changelog.count("\n## ") == 1
    assert "32.0.30" not in changelog
