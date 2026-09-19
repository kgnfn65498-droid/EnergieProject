from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"


def test_32456_release_identity_and_pm_version_are_consistent():
    # Regression name retained: 32.4.57 must carry the 32.4.56 contract forward
    # while publishing the new coherent release identity.
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.57"
    assert (PM / "VERSION.txt").read_text(encoding="utf-8").strip() == "2.0.0-rc45"
    assert 'version: "32.4.57"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.57"' in (APP / "main.py").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.4.57"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")


def test_32456_documentation_records_process_workspace_and_startup_recovery():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP_V10.md").read_text(encoding="utf-8")
    agreements = (ROOT / "PROJECT_AFSPRAKEN.md").read_text(encoding="utf-8")

    assert "## 32.4.56" in changelog
    assert "## 32.4.57" in changelog
    assert "Inbox/process" in changelog
    assert "startup recovery" in changelog.lower()
    assert "32.4.56" in roadmap
    assert "Inbox/process" in roadmap
    assert "Inbox/process" in agreements
    assert "retentie=1" in agreements or "retentie = 1" in agreements
