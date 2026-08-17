import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "slimmemeterportal_import/rootfs/app/assistant_runtime_probe.py"
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_module(name="assistant_runtime_probe_mount_timing_test"):
    spec = importlib.util.spec_from_file_location(name, MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_acceptance_path_is_resolved_from_live_nas_mount_at_probe_time():
    m = load_module("probe_live_nas_path")
    calls = []

    def fake_wait_for_roots(*, attempts, delay_seconds):
        calls.append((attempts, delay_seconds))
        mount = Path("/share/Project Energie")
        layout = mount / "EnergieProject"
        return mount, layout

    target = m.resolve_runtime_acceptance_path(fake_wait_for_roots)
    assert calls == [(60, 5.0)]
    assert target == Path(
        "/share/Project Energie/EnergieProject/Inbox/logs/assistant_runtime_acceptance.json"
    )


def test_main_resolves_acceptance_path_at_probe_time_and_has_no_import_time_absolute_target():
    source = MAIN.read_text(encoding="utf-8")
    assert "resolve_runtime_acceptance_path(wait_for_existing_nas_roots)" in source
    assert "ASSISTANT_RUNTIME_ACCEPTANCE_PATH =" not in source
    assert "acceptance_path: Path | None = None" in source


def test_release_identity_is_v3233_mount_timing_hotfix():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.13"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    root_changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_changelog = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert 'version: "32.3.13"' in config
    assert 'APP_VERSION = "32.3.13"' in main
    assert root_changelog.startswith("## 32.3.13 — Operating modes enforced")
    assert addon_changelog.startswith("# Changelog\n\n## 32.3.13")
