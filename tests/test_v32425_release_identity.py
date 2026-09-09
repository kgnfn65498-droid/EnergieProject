from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"


def test_32425_release_identity_and_core_boundary():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.25"
    assert 'version: "32.4.25"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (APP / "main.py").read_text(encoding="utf-8")
    mode = (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.25"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in main
    assert 'TARGET_RELEASE_VERSION = "32.4.25"' in mode
    assert (APP / "projectmanager_v2/VERSION.txt").read_text(encoding="utf-8").strip() == "2.0.0-rc22"


def test_32425_current_release_contract_and_changelog():
    import release_test_contract as contract
    assert contract.CURRENT_RELEASE == "32.4.25"
    assert contract.CURRENT_PM_VERSION == "2.0.0-rc22"
    root_log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_log = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_log.startswith("## 32.4.25")
    assert addon_log.startswith("# Changelog\n\n## 32.4.25")
