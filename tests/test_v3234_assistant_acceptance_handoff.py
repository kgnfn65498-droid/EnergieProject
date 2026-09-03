import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "slimmemeterportal_import/rootfs/app/assistant_runtime_probe.py"


def load_module(name="assistant_runtime_probe_handoff_test"):
    spec = importlib.util.spec_from_file_location(name, MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_acceptance_uses_writable_inbox_log_handoff_not_projectmanager_state():
    m = load_module()

    def fake_wait_for_roots(*, attempts, delay_seconds):
        assert (attempts, delay_seconds) == (60, 5.0)
        mount = Path("/share/Project Energie")
        layout = mount / "EnergieProject"
        return mount, layout

    target = m.resolve_runtime_acceptance_path(fake_wait_for_roots)
    assert target == Path(
        "/share/Project Energie/EnergieProject/Inbox/logs/assistant_runtime_acceptance.json"
    )
    assert "Data/03_Systeem/Projectmanager/State" not in str(target)


def test_release_identity_is_v3234_handoff_hotfix():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.24"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert 'version: "32.3.24"' in config
    assert 'APP_VERSION = "32.3.24"' in main
    assert changelog.startswith("## 32.3.24")
    assert addon.startswith("# Changelog\n\n## 32.3.24")
