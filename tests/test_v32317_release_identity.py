from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_identity_is_v32317():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.17"
    assert 'version: "32.3.17"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.3.17"' in (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.17"' in (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")


def test_v32317_changelog_documents_idempotent_fail_closed_publication():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_change = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_change.startswith("## 32.3.17 — Idempotent GitHub publication")
    section = root_change.split("## 32.3.16", 1)[0].lower()
    assert "idempotent" in section
    assert "targetmanifest" in section
    assert "fail-closed" in section
    assert "risicogestuurd" in section
    assert "## 32.3.17" in addon_change.splitlines()[:5]
