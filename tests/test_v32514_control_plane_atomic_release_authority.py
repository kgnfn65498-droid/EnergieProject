from __future__ import annotations

import json
import sys
from pathlib import Path

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


def _release_request(version="32.5.13", *, rid="a"*32):
    return {
        "schema":"energie_control_plane_release_request_v1",
        "authorization":"release_controller",
        "action":"native_mcp_reload",
        "container":"energie-filesystem-mcp",
        "request_id":rid,
        "release_id":version+":dee215af80e1",
        "generation":"gen-513",
        "release_version":version,
        "artifact_sha256":"d"*64,
        "expected_fingerprint":"e"*64,
    }


def _plane(tmp_path: Path, request: dict, *, stale_bind_version="32.5.12"):
    inbox=tmp_path/"Inbox"; approved=tmp_path/"approved.json"; version=tmp_path/"VERSIE.txt"; evidence=tmp_path/"RuntimeEvidence"
    approved.write_text('{"items": []}\n', encoding="utf-8")
    version.write_text(stale_bind_version+"\n", encoding="utf-8")
    evidence.mkdir()
    _write(inbox/"control_plane/requests/native_mcp_reload.json", request)
    _write(inbox/"release_controller/current.json", {
        "phase":"COMPLETE","status":"COMPLETE","release_id":request["release_id"],
        "generation":request["generation"],"to_version":request["release_version"],
        "artifact_sha256":request["artifact_sha256"],
    })
    _write(inbox/"atomic_app_swap_state.json", {
        "state":"ACCEPTED","from_version":"32.5.12","to_version":request["release_version"],
        "artifact_sha256":request["artifact_sha256"],
    })
    _write(inbox/"native_mcp_runtime/runtime_guard.json", {
        "status":"RELOAD_REQUIRED","reload_required":True,"expected_fingerprint":request["expected_fingerprint"],
    })
    return cp.ControlPlane(
        inbox=inbox, approved_queue=approved, version_path=version, runtime_evidence=evidence,
        host_project_root="/share/Energie_NAS/EnergieProject", docker=None,
    ), inbox, evidence


def test_release_reload_uses_atomic_authority_when_version_bind_is_stale(tmp_path):
    request=_release_request()

    class Docker:
        def __init__(self): self.restarts=0
        def ping(self): return {"ok":True}
        def inspect_container(self,name): return {"State":{"Running":True}}
        def restart_container(self,name,timeout=30): self.restarts+=1; return {"ok":True}

    plane,inbox,evidence=_plane(tmp_path,request)
    docker=Docker(); plane.docker=docker
    plane._wait_json=lambda *args,**kwargs: {
        "schema":"energie_native_mcp_runtime_v3","fingerprint":request["expected_fingerprint"]
    }
    result=plane.process_once()
    assert docker.restarts==1
    assert result and result[0]["status"]=="GREEN"
    assert result[0]["request_id"]==request["request_id"]
    assert not list((inbox/"projectmanager_v2/RuntimeV2/control_plane_archive").glob("native_mcp_reload.stale.*"))


def test_stale_release_scoped_request_uses_controller_owner_not_stale_bind(tmp_path):
    current=_release_request("32.5.13",rid="b"*32)
    stale=_release_request("32.5.12",rid="c"*32)
    plane,inbox,_=_plane(tmp_path,stale,stale_bind_version="32.5.12")
    _write(inbox/"release_controller/current.json", {
        "phase":"COMPLETE","status":"COMPLETE","release_id":current["release_id"],
        "generation":current["generation"],"to_version":current["release_version"],
        "artifact_sha256":current["artifact_sha256"],
    })
    assert plane.process_once()==[]
    assert not (inbox/"control_plane/requests/native_mcp_reload.json").exists()
    archived=list((inbox/"projectmanager_v2/RuntimeV2/control_plane_archive").glob("native_mcp_reload.stale.32.5.12.*.json"))
    assert len(archived)==1


def test_release_authority_rejects_atomic_artifact_mismatch(tmp_path):
    from control_plane_release_bridge import authorize_release_native_request
    request=_release_request()
    plane,inbox,_=_plane(tmp_path,request)
    _write(inbox/"atomic_app_swap_state.json", {
        "state":"ACCEPTED","from_version":"32.5.12","to_version":"32.5.13","artifact_sha256":"f"*64,
    })
    try:
        authorize_release_native_request(
            request_path=inbox/"control_plane/requests/native_mcp_reload.json",
            controller_state_path=inbox/"release_controller/current.json",
            version_path=plane.version_path,
            runtime_guard_path=inbox/"native_mcp_runtime/runtime_guard.json",
            atomic_state_path=inbox/"atomic_app_swap_state.json",
        )
    except RuntimeError as exc:
        assert "authorization rejected" in str(exc)
    else:
        raise AssertionError("atomic mismatch must fail closed")
