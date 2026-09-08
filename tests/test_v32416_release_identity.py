from pathlib import Path
from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32416_release_identity_is_consistent():
    assert CURRENT_RELEASE == '32.4.16'
    assert CURRENT_PM_VERSION == '2.0.0-rc13'
    assert (ROOT / 'VERSIE.txt').read_text().strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == CURRENT_PM_VERSION


def test_v32416_learning_contract_is_persisted_in_docs_and_kb_sync():
    changelog = (ROOT / 'CHANGELOG.md').read_text()
    agreements = (ROOT / 'PROJECT_AFSPRAKEN.md').read_text()
    roadmap = (ROOT / 'ROADMAP_V10.md').read_text()
    manager = (PM / 'manager_service.py').read_text()
    for phrase in ('root cause', 'regressietest'):
        assert phrase.lower() in changelog.lower()
        assert phrase.lower() in agreements.lower()
    assert 'v32.4.16' in roadmap
    assert 'Ontwikkelproceslessen 32.4.16' in manager
    assert 'release_hold_tmp' in manager
