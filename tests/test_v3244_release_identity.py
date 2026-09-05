from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v3244_release_and_manager_identity():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == '32.4.4'
    assert 'version: "32.4.4"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert 'APP_VERSION = "32.4.4"' in (APP / 'main.py').read_text()
    assert 'TARGET_RELEASE_VERSION = "32.4.4"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == '2.0.0-rc4'
    assert (ROOT / 'CHANGELOG.md').read_text().startswith('## 32.4.4')
    assert (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text().startswith('# Changelog\n\n## 32.4.4')
