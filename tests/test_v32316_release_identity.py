from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32316_release_identity_is_preserved_in_history():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.16 — Crash Recovery Maintenance integration" in root_change


def test_v32316_changelog_documents_mode_completion_and_13_month_retention():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.16 — Crash Recovery Maintenance integration" in root_change
    first_section = root_change.split("## 32.3.15", 1)[0].lower()
    assert "maintenance" in first_section
    assert "user" in first_section
    assert "development" in first_section
    assert "13 maanden" in first_section
