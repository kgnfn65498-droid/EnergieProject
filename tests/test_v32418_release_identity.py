from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32418_release_identity_is_preserved_historically():
    changelog = (ROOT / 'CHANGELOG.md').read_text()
    section = changelog.split('## 32.4.18', 1)[1].split('\n## ', 1)[0]
    assert '2.0.0-rc15' in section
    assert 'transactionele release-closure' in section.lower()


def test_v32418_release_closure_lessons_are_persisted():
    changelog = (ROOT / 'CHANGELOG.md').read_text().lower()
    agreements = (ROOT / 'PROJECT_AFSPRAKEN.md').read_text().lower()
    roadmap = (ROOT / 'ROADMAP_V10.md').read_text().lower()
    manager = (PM / 'manager_service.py').read_text().lower()
    for phrase in ('restart', 'live_acceptance', 'canonieke publicatiestatus', 'sigkill'):
        assert phrase in changelog
    assert 'twee opeenvolgende releases' in agreements
    assert '32.4.18' in roadmap
    assert 'ontwikkelproceslessen 32.4.18' in manager
