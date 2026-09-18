from pathlib import Path
import release_test_contract as contract

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'


def test_v32455_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == contract.CURRENT_RELEASE
    assert f'CURRENT_RELEASE = "{contract.CURRENT_RELEASE}"' in (ROOT / 'release_test_contract.py').read_text(encoding='utf-8')
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')


def test_v32455_does_not_ship_legacy_same_version_publication_bridge():
    assert not (ROOT / 'tools/same_version_publication_bridge.py').exists()
