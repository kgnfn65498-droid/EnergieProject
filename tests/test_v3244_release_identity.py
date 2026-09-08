from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v3244_release_and_manager_identity():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == CURRENT_PM_VERSION
    assert (ROOT / 'CHANGELOG.md').read_text().startswith(f'## {CURRENT_RELEASE}')
    assert (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text().startswith(f'# Changelog\n\n## {CURRENT_RELEASE}')
