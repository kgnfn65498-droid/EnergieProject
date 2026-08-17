from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32318_release_identity_is_preserved_in_history():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.18 — Live mode GUI refresh" in root_change


def test_v32318_changelog_documents_live_gui_refresh():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = root_change.split("## 32.3.18", 1)[1].split("## 32.3.17", 1)[0].lower()
    assert "refresh" in section
    assert "release-hold" in section
    assert "fail-closed" in section
