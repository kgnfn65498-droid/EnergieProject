from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v32410_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.10'
    config = (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'version: "32.4.10"' in config
    assert 'github_publication_enabled: true' in config
    assert 'APP_VERSION = "32.4.10"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.10"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc7'


def test_v32410_release_contains_reconciliation_and_proactive_modules():
    assert (PM / 'state_reconciliation.py').is_file()
    assert (PM / 'proactive_policy.py').is_file()
    assert (ROOT / 'tests/test_v32410_state_lifecycle.py').is_file()
    assert (ROOT / 'tests/test_v32410_state_reconciliation.py').is_file()
    assert (ROOT / 'tests/test_v32410_proactive_policy.py').is_file()
    assert (ROOT / 'tests/test_v32410_intake_followup.py').is_file()
    assert (ROOT / 'tests/test_v32410_proactive_runtime.py').is_file()


def test_v32410_changelog_contract():
    root_changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    addon_changelog = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8')
    assert root_changelog.startswith('## 32.4.10 — Proactive PM + state reconciliation')
    assert addon_changelog.startswith('# Changelog\n\n## 32.4.10')
    assert addon_changelog.count('\n## ') == 1
