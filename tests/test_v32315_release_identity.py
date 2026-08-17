from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32315_release_identity_is_preserved_in_history():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.15 — Ingress GUI navigation" in root_change


def test_v32315_changelog_is_gui_only_safety_preserving_release():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = root_change.split("## 32.3.15 — Ingress GUI navigation", 1)[1].split("## 32.3.14", 1)[0]
    assert "Post/Redirect/Get" in section
    assert "structured JSON" in section
    assert "basis-profile" in section
    assert "No controller, HOLD, scheduler, watcher or month-close semantics changed." in section
