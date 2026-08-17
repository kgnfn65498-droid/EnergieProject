from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32317_release_identity_is_preserved_in_history():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.17 — Idempotent GitHub publication" in root_change


def test_v32317_changelog_documents_idempotent_fail_closed_publication():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = root_change.split("## 32.3.17", 1)[1].split("## 32.3.16", 1)[0].lower()
    assert "idempotent" in section
    assert "targetmanifest" in section
    assert "fail-closed" in section
    assert "risicogestuurd" in section
