from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32424_release_identity_and_core_revision():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == '32.4.24'
    config = (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    main = (ROOT / 'slimmemeterportal_import/rootfs/app/main.py').read_text()
    mode = (ROOT / 'slimmemeterportal_import/rootfs/app/mode_entrypoint.py').read_text()
    pm_version = (ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').read_text().strip()
    assert 'version: "32.4.24"' in config
    assert 'APP_VERSION = "32.4.24"' in main
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in main
    assert 'TARGET_RELEASE_VERSION = "32.4.24"' in mode
    assert pm_version == '2.0.0-rc21'


def test_v32424_changelogs_describe_exact_maintenance_scope():
    root = (ROOT / 'CHANGELOG.md').read_text()
    addon = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text()
    assert root.startswith('## 32.4.24')
    assert addon.startswith('# Changelog\n\n## 32.4.24')
    for text in (root, addon):
        lowered = text.lower()
        assert 'legacy' in lowered
        assert 'non-mutating' in lowered or 'non_mutating' in lowered
        assert 'roadmap' in lowered
