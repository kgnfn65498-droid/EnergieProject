from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_identity_is_v32315():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.15"
    assert 'version: "32.3.15"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.3.15"' in (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.15"' in (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")


def test_v32315_changelog_is_gui_only_safety_preserving_release():
    root_change = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_change = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert root_change.startswith("## 32.3.15 — Ingress GUI navigation")
    assert "Post/Redirect/Get" in root_change
    assert "structured JSON" in root_change
    assert "basis-profile" in root_change
    assert "No controller, HOLD, scheduler, watcher or month-close semantics changed." in root_change
    assert "## 32.3.15" in addon_change.splitlines()[:5]
