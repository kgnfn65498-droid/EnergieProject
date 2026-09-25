from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
CP_DIR = TOOLS / "control_plane"
for path in (str(TOOLS), str(CP_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import control_plane as cp


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _controller(version="32.5.15", sha="a" * 64):
    return {
        "phase": "COMPLETE",
        "status": "COMPLETE",
        "release_id": f"{version}:{sha[:12]}",
        "generation": "gen-515",
        "to_version": version,
        "artifact_sha256": sha,
    }


def _atomic(version="32.5.15", sha="a" * 64):
    return {
        "state": "ACCEPTED",
        "from_version": "32.5.14",
        "to_version": version,
        "artifact_sha256": sha,
    }


def _guard(fp="b" * 64):
    return {
        "status": "RELOAD_REQUIRED",
        "ready": False,
        "reload_required": True,
        "expected_fingerprint": fp,
        "runtime_fingerprint": "c" * 64,
    }


def test_stable_release_authority_works_before_type2_path_migration(tmp_path):
    inbox = tmp_path / "Inbox"
    release_root = tmp_path / "ReleaseControllerDestination"
    native_root = tmp_path / "NativeDestination"
    _write(inbox / "release_controller/current.json", _controller())
    _write(inbox / "atomic_app_swap_state.json", _atomic())
    _write(inbox / "native_mcp_runtime/runtime_guard.json", _guard())

    paths = cp.stable_release_paths(inbox, release_root, native_root)
    assert paths["controller"] == inbox / "release_controller/current.json"
    assert paths["atomic"] == inbox / "atomic_app_swap_state.json"
    assert paths["native_guard"] == inbox / "native_mcp_runtime/runtime_guard.json"
    assert cp.stable_release_version(inbox, release_root) == "32.5.15"


def test_stable_release_authority_works_after_type2_path_migration(tmp_path):
    inbox = tmp_path / "Inbox"
    release_root = tmp_path / "ReleaseControllerDestination"
    native_root = tmp_path / "NativeDestination"
    _write(release_root / "current.json", _controller())
    _write(release_root / "State/atomic_app_swap_state.json", _atomic())
    _write(native_root / "runtime_guard.json", _guard())

    paths = cp.stable_release_paths(inbox, release_root, native_root)
    assert paths["controller"] == release_root / "current.json"
    assert paths["atomic"] == release_root / "State/atomic_app_swap_state.json"
    assert paths["native_guard"] == native_root / "runtime_guard.json"
    assert cp.stable_release_version(inbox, release_root) == "32.5.15"


def test_dual_pre_post_migration_state_mismatch_fails_closed(tmp_path):
    inbox = tmp_path / "Inbox"
    release_root = tmp_path / "ReleaseControllerDestination"
    _write(inbox / "release_controller/current.json", _controller("32.5.14"))
    _write(release_root / "current.json", _controller("32.5.15"))
    _write(inbox / "atomic_app_swap_state.json", _atomic("32.5.14"))
    _write(release_root / "State/atomic_app_swap_state.json", _atomic("32.5.15"))

    with pytest.raises(RuntimeError, match="pre/post-migratie state mismatch"):
        cp.stable_release_version(inbox, release_root)


def test_control_plane_production_compose_has_no_atomic_app_file_bind():
    compose = (CP_DIR / "docker-compose.containerstation.yml").read_text(encoding="utf-8")
    assert "/share/Energie_NAS/EnergieProject/App/" not in compose
    assert "/energy-version/VERSIE.txt" not in compose
    assert "--version" not in compose


def test_control_plane_runtime_code_never_reads_version_bind():
    source = (CP_DIR / "control_plane.py").read_text(encoding="utf-8")
    qnap = (CP_DIR / "qnap_control_plane_bootstrap.py").read_text(encoding="utf-8")
    bridge = (CP_DIR / "control_plane_release_bridge.py").read_text(encoding="utf-8")
    forbidden = (
        "self.version_path.read_text",
        "/energy-version/VERSIE.txt",
    )
    for token in forbidden:
        assert token not in source
        assert token not in qnap
        assert token not in bridge


def test_release_scoped_reload_uses_post_migration_state_without_version_file(tmp_path):
    request = {
        "schema": "energie_control_plane_release_request_v1",
        "authorization": "release_controller",
        "action": "native_mcp_reload",
        "container": "energie-filesystem-mcp",
        "request_id": "d" * 32,
        "release_id": "32.5.15:" + "a" * 12,
        "generation": "gen-515",
        "release_version": "32.5.15",
        "artifact_sha256": "a" * 64,
        "expected_fingerprint": "b" * 64,
    }
    inbox = tmp_path / "Inbox"
    release_root = tmp_path / "ReleaseControllerDestination"
    native_root = tmp_path / "NativeDestination"
    approved = tmp_path / "approved.json"
    evidence = tmp_path / "RuntimeEvidence"
    approved.write_text('{"items": []}\n', encoding="utf-8")
    evidence.mkdir()
    _write(inbox / "control_plane/requests/native_mcp_reload.json", request)
    _write(release_root / "current.json", _controller())
    _write(release_root / "State/atomic_app_swap_state.json", _atomic())
    _write(native_root / "runtime_guard.json", _guard())

    class Docker:
        def __init__(self): self.restarts = 0
        def ping(self): return {"ok": True}
        def inspect_container(self, name): return {"State": {"Running": True}}
        def restart_container(self, name, timeout=30): self.restarts += 1; return {"ok": True}

    plane = cp.ControlPlane(
        inbox=inbox,
        approved_queue=approved,
        version_path=tmp_path / "DOES_NOT_EXIST.txt",
        runtime_evidence=evidence,
        release_controller_root=release_root,
        native_mcp_runtime_root=native_root,
        host_project_root="/share/Energie_NAS/EnergieProject",
        docker=Docker(),
    )
    plane._wait_json = lambda *args, **kwargs: {
        "schema": "energie_native_mcp_runtime_v3",
        "fingerprint": request["expected_fingerprint"],
    }
    result = plane.process_once()
    assert plane.docker.restarts == 1
    assert result and result[0]["status"] == "GREEN"


def test_legacy_test_version_fallback_rejects_old_production_bind():
    with pytest.raises(RuntimeError, match="production App/VERSIE file authority is retired"):
        cp._isolated_legacy_version_for_tests(Path("/energy-version/VERSIE.txt"))
