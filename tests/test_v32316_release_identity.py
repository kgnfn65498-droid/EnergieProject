from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_identity_is_v32316():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.16"
    assert 'version: "32.3.16"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.3.16"' in (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.16"' in (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")


def test_v32316_changelog_documents_mode_completion_and_13_month_retention():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_change = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_change.startswith("## 32.3.16 — Crash Recovery Maintenance integration")
    first_section = root_change.split("## 32.3.15", 1)[0].lower()
    assert "maintenance" in first_section
    assert "user" in first_section
    assert "development" in first_section
    assert "13 maanden" in first_section
    assert "## 32.3.16" in addon_change.splitlines()[:5]
