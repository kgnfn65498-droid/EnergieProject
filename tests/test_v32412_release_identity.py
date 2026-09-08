from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32412_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.12'
    config = (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'version: "32.4.12"' in config
    assert 'APP_VERSION = "32.4.12"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.12"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc9'


def test_v32412_changelogs_describe_closure_release():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    addon = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8')
    assert root.startswith('## 32.4.12')
    assert addon.startswith('# Changelog\n\n## 32.4.12')
    assert 'runtime truth' in root.lower()
    assert 'maandafsluiting' in root.lower()
    assert '2.0.0-rc9' in root
