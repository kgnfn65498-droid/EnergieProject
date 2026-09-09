from pathlib import Path
from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def _release_tuple(value):
    return tuple(int(part) for part in str(value).split('.'))


def _pm_rc(value):
    return int(str(value).rsplit('rc', 1)[1])


def test_v32420_release_identity_contract_remains_valid_for_successors():
    assert _release_tuple(CURRENT_RELEASE) >= (32, 4, 20)
    assert _pm_rc(CURRENT_PM_VERSION) >= 17
    assert (ROOT / 'VERSIE.txt').read_text().strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == CURRENT_PM_VERSION
