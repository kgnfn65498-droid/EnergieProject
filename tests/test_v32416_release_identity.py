from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32416_release_identity_is_preserved_historically():
    changelog = (ROOT / 'CHANGELOG.md').read_text()
    assert '32.4.16' in changelog


def test_v32416_learning_contract_is_persisted_in_docs_and_kb_sync():
    changelog = (ROOT / 'CHANGELOG.md').read_text()
    agreements = (ROOT / 'PROJECT_AFSPRAKEN.md').read_text()
    roadmap = (ROOT / 'ROADMAP_V10.md').read_text()
    manager = (PM / 'manager_service.py').read_text()
    for phrase in ('root cause', 'regressietest'):
        assert phrase.lower() in changelog.lower()
        assert phrase.lower() in agreements.lower()
    assert 'v32.4.16' in roadmap
    assert 'Ontwikkelproceslessen 32.4.16' in manager
    assert 'release_hold_tmp' in manager
