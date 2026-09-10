from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION

APP = ROOT / 'slimmemeterportal_import/rootfs/app'


def test_v32423_release_and_pm_identity_are_synchronized():
    assert CURRENT_RELEASE == '32.4.32'
    assert CURRENT_PM_VERSION == '2.0.0-rc22'
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == CURRENT_RELEASE
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert (APP / 'projectmanager_v2/VERSION.txt').read_text(encoding='utf-8').strip() == CURRENT_PM_VERSION


def test_v32423_release_documents_audit_closure_and_pre_325_voice_gate():
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    addon_changelog = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8')
    roadmap = (ROOT / 'ROADMAP_V10.md').read_text(encoding='utf-8')
    agreements = (ROOT / 'PROJECT_AFSPRAKEN.md').read_text(encoding='utf-8')
    assert changelog.startswith('## 32.4.32')
    assert addon_changelog.startswith('# Changelog\n\n## 32.4.32')
    assert 'CLOSED_VALID' in changelog and 'UNKNOWN' in changelog
    assert 'voice-live-acceptance' in roadmap
    assert 'new-chat-handover-live' in roadmap
    assert 'ngrok' in agreements.lower() and '8099' in agreements
    assert '9.4-core3' in agreements
