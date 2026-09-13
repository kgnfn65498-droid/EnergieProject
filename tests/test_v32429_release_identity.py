from pathlib import Path
import release_test_contract as contract

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"

def test_32429_release_identity_is_synchronized():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_RELEASE
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / "main.py").read_text(encoding="utf-8")
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert contract.CURRENT_PM_VERSION == "2.0.0-rc39"
    assert (APP / "projectmanager_v2/VERSION.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_PM_VERSION
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in (APP / "main.py").read_text(encoding="utf-8")

def test_32429_changelog_documents_timeout_and_observability():
    text=(ROOT/'CHANGELOG.md').read_text(encoding='utf-8').lower()
    assert text.startswith(f'## {contract.CURRENT_RELEASE}')
    assert 'checkpoint' in text and '25 minuten' in text and 'fail-closed' in text
    assert 'project_clearup_runtime.json' in text
