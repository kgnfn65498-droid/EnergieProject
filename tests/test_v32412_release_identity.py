from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32412_changelog_remains_historical():
    root = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert '## 32.4.12 — functionele closure en runtime truth' in root
    assert 'Projectmanager naar `2.0.0-rc9`' in root


def test_v32412_plan_remains_historical():
    plan = ROOT / 'docs/superpowers/plans/2026-09-08-32-4-12-closure.md'
    text = plan.read_text(encoding='utf-8')
    assert '# EnergieProject 32.4.12 Closure Implementation Plan' in text
    assert 'bump 32.4.12 + PM rc9' in text
