from pathlib import Path

from release_test_contract import CURRENT_PM_VERSION, CURRENT_RELEASE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32413_release_identity_is_consistent():
    assert CURRENT_RELEASE == '32.4.13'
    assert CURRENT_PM_VERSION == '2.0.0-rc10'
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == CURRENT_RELEASE
    config = (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert f'version: "{CURRENT_RELEASE}"' in config
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == CURRENT_PM_VERSION


def test_v32413_changelogs_describe_regie_closure():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    addon = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8')
    assert root.startswith('## 32.4.13')
    assert addon.startswith('# Changelog\n\n## 32.4.13')
    for phrase in ('LIVE_ACCEPTANCE', 'transactioneel', 'Home Assistant-GUI', '2.0.0-rc10'):
        assert phrase in root
