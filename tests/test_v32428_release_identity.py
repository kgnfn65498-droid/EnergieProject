from pathlib import Path
import release_test_contract as contract

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"

def test_32428_release_identity_is_synchronized():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.44"
    assert 'version: "32.4.44"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.44"' in (APP / "main.py").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.4.44"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert contract.CURRENT_RELEASE == "32.4.44"
    assert contract.CURRENT_PM_VERSION == "2.0.0-rc31"
    assert (APP / "projectmanager_v2/VERSION.txt").read_text(encoding="utf-8").strip() == "2.0.0-rc31"
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in (APP / "main.py").read_text(encoding="utf-8")

def test_32428_changelog_describes_pm_observation_dependency_fix():
    root_log=(ROOT/'CHANGELOG.md').read_text(encoding='utf-8').lower()
    addon_log=(ROOT/'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8').lower()
    assert root_log.startswith('## 32.4.44')
    assert addon_log.startswith('# changelog\n\n## 32.4.44')
    text=root_log+addon_log
    assert 'projectmanager' in text and 'snapshot' in text and 'fail-closed' in text
