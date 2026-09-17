from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'


def test_v32455_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.55'
    assert 'CURRENT_RELEASE = "32.4.55"' in (ROOT / 'release_test_contract.py').read_text(encoding='utf-8')
    assert 'version: "32.4.55"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.55"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.55"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')


def test_v32455_does_not_ship_legacy_same_version_publication_bridge():
    assert not (ROOT / 'tools/same_version_publication_bridge.py').exists()
