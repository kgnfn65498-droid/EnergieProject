from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools/release_runtime_adapter.py"
EXPECTED_32523_ADAPTER_SHA256 = "c3483df9d4b7f8b761d71b2714c855c93efa5290e9883b1808da138cdadca1be"


def _load_adapter():
    assert hashlib.sha256(ADAPTER.read_bytes()).hexdigest() == EXPECTED_32523_ADAPTER_SHA256
    spec = importlib.util.spec_from_file_location("v32523_predecessor_runtime_adapter", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReadyGuard:
    def probe(self, root):
        return {"ready": True, "expected_fingerprint": "a" * 64, "runtime_fingerprint": "a" * 64}


def test_v32523_predecessor_controller_prepares_control_plane_when_installing_v32524(tmp_path, monkeypatch):
    mod = _load_adapter()
    monkeypatch.setattr(mod.native_mcp_runtime_contract_hotfix, "apply", lambda root: {
        "status": "GREEN", "command_forwarding_current": True,
    })
    calls = []
    coordinator = mod.NativeRuntimeCoordinator(
        tmp_path, ReadyGuard(), lambda: True,
        control_plane_prepare=lambda: calls.append("prepare") or {"status": "GREEN", "binding_current": True},
    )
    state = SimpleNamespace(
        release_id="32.5.24:artifact", generation="gen-524", artifact_sha256="b" * 64, to_version="32.5.24"
    )
    out = coordinator.align(state)
    assert out.status == "GREEN"
    assert calls == ["prepare"]
