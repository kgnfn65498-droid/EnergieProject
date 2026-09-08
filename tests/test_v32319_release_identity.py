from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_identity_is_v32319():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")


def test_v32319_changelog_documents_crash_recovery_hardening_and_auto_hold():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = root_change.split("## 32.3.18", 1)[0].lower()
    assert root_change.startswith(f"## {CURRENT_RELEASE}")
    assert "maintenance" in section
    assert "automatische" in section
    assert "hold" in section
    assert "cleanup" in section
