from pathlib import Path
import release_test_contract as contract

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"


def test_32426_release_identity_is_synchronized():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.26"
    assert 'version: "32.4.26"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.26"' in (APP / "main.py").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.4.26"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert contract.CURRENT_RELEASE == "32.4.26"
    assert contract.CURRENT_PM_VERSION == "2.0.0-rc22"
    assert (APP / "projectmanager_v2/VERSION.txt").read_text(encoding="utf-8").strip() == "2.0.0-rc22"
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in (APP / "main.py").read_text(encoding="utf-8")


def test_32426_changelog_describes_indexed_clearup_dependency_audit():
    root_log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_log = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_log.startswith("## 32.4.26")
    assert addon_log.startswith("# Changelog\n\n## 32.4.26")
    text = (root_log + addon_log).lower()
    assert "dependency" in text and "index" in text and "fail-closed" in text
