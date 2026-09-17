from pathlib import Path
import release_test_contract as contract

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"


def test_32425_release_identity_and_core_boundary():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_RELEASE
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (APP / "main.py").read_text(encoding="utf-8")
    mode = (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in main
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in mode
    assert (APP / "projectmanager_v2/VERSION.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_PM_VERSION


def test_32425_current_release_contract_and_changelog():
    assert contract.CURRENT_PM_VERSION == "2.0.0-rc42"
    root_log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_log = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_log.startswith(f"## {contract.CURRENT_RELEASE}")
    assert addon_log.startswith(f"# Changelog\n\n## {contract.CURRENT_RELEASE}")
