from pathlib import Path
from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'

def test_v32417_release_identity_is_consistent():
    assert CURRENT_RELEASE == '32.4.17'
    assert CURRENT_PM_VERSION == '2.0.0-rc14'
    assert (ROOT / 'VERSIE.txt').read_text().strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == CURRENT_PM_VERSION

def test_v32417_live_lessons_are_persisted():
    changelog=(ROOT/'CHANGELOG.md').read_text().lower()
    agreements=(ROOT/'PROJECT_AFSPRAKEN.md').read_text().lower()
    roadmap=(ROOT/'ROADMAP_V10.md').read_text().lower()
    manager=(PM/'manager_service.py').read_text().lower()
    for phrase in ('watcher', 'publisher', 'release-validation', 'root cause'):
        assert phrase in changelog
    assert 'bounded' in agreements
    assert '32.4.17' in roadmap
    assert 'ontwikkelproceslessen 32.4.17' in manager
