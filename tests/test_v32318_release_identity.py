from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_identity_is_v32318():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.18"
    assert 'version: "32.3.18"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.3.18"' in (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.18"' in (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")


def test_v32318_changelog_documents_live_gui_refresh():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_change = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_change.startswith("## 32.3.18 — Live mode GUI refresh")
    section = root_change.split("## 32.3.17", 1)[0].lower()
    assert "refresh" in section
    assert "release-hold" in section
    assert "fail-closed" in section
    assert "## 32.3.18" in addon_change.splitlines()[:5]
