from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _section(text: str, version: str) -> str:
    marker = f'## {version}'
    start = text.index(marker)
    next_start = text.find('\n## ', start + len(marker))
    return text[start:] if next_start < 0 else text[start:next_start]


def test_v32414_historical_release_identity_is_preserved_in_changelog():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    section = _section(root, '32.4.14')
    for phrase in ('Claude Cowork', 'approval', 'LIVE_ACCEPTANCE', '2.0.0-rc11'):
        assert phrase in section
