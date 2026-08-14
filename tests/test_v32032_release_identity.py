import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
VERSIE = ROOT / "VERSIE.txt"
CHANGELOG = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG = ROOT / "slimmemeterportal_import/CHANGELOG.md"


def test_v32032_release_identity_is_synchronized():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    versie = VERSIE.read_text(encoding="utf-8").strip()

    assert versie == "32.0.32"
    assert 'version: "32.0.32"' in config
    assert 'APP_VERSION = "32.0.32"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main


def test_v32032_crash_recovery_filename_contract_is_present():
    main = MAIN.read_text(encoding="utf-8")
    assert '%Y-%m-%d %H.%M CrashRecovery EnergieProject.zip' in main
    assert 'EnergieProject_Complete_Crash_Recovery_' not in main


def test_v32032_changelog_mentions_watcher_cleanup_fix():
    changelog = CHANGELOG.read_text(encoding="utf-8")
    assert changelog.startswith("## v32.0.32 — Crash Recovery watcher-cleanup")
    assert "QNAP/Docker-watcher" in changelog
    assert "finalize_month" in changelog


def test_v32032_addon_changelog_is_current_release_only():
    changelog = ADDON_CHANGELOG.read_text(encoding="utf-8")
    assert "## 32.0.32 - Crash Recovery watcher-cleanup" in changelog
    assert changelog.count("\n## ") == 1
    assert "\n## 32.0.31" not in changelog
