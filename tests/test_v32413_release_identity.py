from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _section(text: str, version: str) -> str:
    marker = f'## {version}'
    start = text.index(marker)
    next_start = text.find('\n## ', start + len(marker))
    return text[start:] if next_start < 0 else text[start:next_start]


def test_v32413_historical_release_identity_is_preserved_in_changelog():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    root_413 = _section(root, '32.4.13')
    assert root_413.startswith('## 32.4.13')
    for phrase in ('LIVE_ACCEPTANCE', 'transactioneel', 'Home Assistant-GUI', '2.0.0-rc10'):
        assert phrase in root_413
