from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32415_release_identity_remains_in_historical_changelog():
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert '## 32.4.15' in changelog
    assert '2.0.0-rc12' in changelog


def test_v32415_voice_and_handover_closure_remains_documented():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    section = root.split('## 32.4.15', 1)[1].split('\n## ', 1)[0]
    for phrase in ('Voice Mode', 'LIVE_ACCEPTANCE', 'nieuwe chat', '2.0.0-rc12'):
        assert phrase in section
