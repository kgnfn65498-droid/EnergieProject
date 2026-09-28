from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for p in (str(TOOLS), str(APP), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from release_controller import ReleaseState
from ha_delivery_adapter import HADelivery
import github_publisher_binding as publisher_binding
import system_path_contract
import clearup_type3_service as type3


def _w(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _j(path: Path, value: dict) -> None:
    _w(path, json.dumps(value, sort_keys=True) + "\n")


def _activation(root: Path, key: str, source: str, destination: str) -> None:
    _j(root / "Data/03_Systeem/Projectmanager/ClearUp/PathActivation" / f"{key}.json", {
        "schema": "energie_clearup_system_path_contract_v1",
        "active": True,
        "key": key,
        "source": source,
        "destination": destination,
        "clearup_id": "ClearUp_011",
        "plan_sha256": "x",
    })


def _release_zip(path: Path, version: str = "32.5.26") -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = "d41d8cd98f00b204e9800998ecf8427e  empty\n"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSIE.txt", version + "\n")
        z.writestr("MANIFEST.sha256", manifest)
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(manifest.encode()).hexdigest()


def _state(sha: str, name: str) -> ReleaseState:
    return ReleaseState(
        release_id=f"32.5.26:{sha[:12]}", generation="g" * 32,
        from_version="32.5.25", to_version="32.5.26",
        artifact_sha256=sha, artifact_name=name,
        phase="ACCEPTED", status="ACTIVE", step=8,
        started_at_epoch=time.time(), phase_started_at_epoch=time.time(), updated_at_epoch=time.time(), evidence=[],
    )


def test_32526_active_file_contract_never_falls_back_when_canonical_payload_absent(tmp_path):
    root = tmp_path / "p"
    canonical = root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication"
    canonical.mkdir(parents=True)
    _activation(root, "github_publication_state", "Inbox/github_publication_state.json", "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json")
    resolved = system_path_contract.project_system_path(root, "Inbox/github_publication_state.json")
    assert resolved == canonical / "github_publication_state.json"
    assert not resolved.exists()

    script = ROOT / "tools/system_path_contract.sh"
    cmd = f'. "{script}"; energie_system_path "{root}" github_publication_state Inbox/github_publication_state.json Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json'
    out = subprocess.check_output(["sh", "-c", cmd], text=True).strip()
    assert out == str(resolved)


def _seed_delivery(root: Path):
    _w(root / "App/VERSIE.txt", "32.5.25\n")
    _w(root / "App/MANIFEST.sha256", "active-manifest\n")
    _w(root / "App.__rollback_32.5.25/MANIFEST.sha256", "active-manifest\n")
    artifact = root / "Inbox/processing/EnergieProject_v32.5.26.zip"
    sha, _ = _release_zip(artifact)
    s = _state(sha, artifact.name)
    pubdir = root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication"
    pubdir.mkdir(parents=True)
    _activation(root, "github_publication_state", "Inbox/github_publication_state.json", "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json")
    _activation(root, "github_publisher_state", "Inbox/github_publisher_state.json", "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json")
    _activation(root, "ha_runtime", "Inbox/ha_runtime", "Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant")
    (root / "Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant").mkdir(parents=True)
    return artifact, s


def test_32526_exact_legacy_publication_is_reconciled_and_release_archives(tmp_path):
    root = tmp_path / "p"
    artifact, state = _seed_delivery(root)
    delivery = HADelivery(root, timeout_seconds=1)
    first = delivery.prepare_pre_target(state)
    assert first.status == "WAITING"
    marker = root / "Inbox/ha_publication_required.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    exact = dict(payload)
    exact.update({"published": True, "target_exact": True, "local_head": "abc123", "remote_head": "abc123"})
    _j(root / "Inbox/github_publication_state.json", exact)
    _j(root / "Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant/current.json", {"version": "32.5.26"})

    out = delivery.align(state)
    assert out.status == "GREEN"
    assert set(out.evidence) >= {"github_target_exact", "ha_runtime_current", "publication_contract_settled", "processed_archived"}
    canonical = root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json"
    result = json.loads(canonical.read_text(encoding="utf-8"))
    assert result["publication_contract_settled"] is True
    assert result["contract_settled_by"] == "release_controller"
    assert not (root / "Inbox/github_publication_state.json").exists()
    assert not marker.exists()
    assert not artifact.exists()
    assert (root / "Inbox/processed" / artifact.name).is_file()


def test_32526_wrong_generation_or_commit_mismatch_is_never_promoted(tmp_path):
    root = tmp_path / "p"
    _, state = _seed_delivery(root)
    delivery = HADelivery(root, timeout_seconds=1)
    delivery.prepare_pre_target(state)
    payload = json.loads((root / "Inbox/ha_publication_required.json").read_text(encoding="utf-8"))
    bad = dict(payload)
    bad.update({"published": True, "target_exact": True, "generation": "WRONG", "local_head": "a", "remote_head": "b"})
    _j(root / "Inbox/github_publication_state.json", bad)
    reconciled = delivery._reconcile_exact_publication(payload)
    assert reconciled == {}
    assert not (root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json").exists()
    assert (root / "Inbox/github_publication_state.json").exists()


def _publisher_info(root: Path, *, current_labels: bool) -> dict:
    ident = publisher_binding._code_identity(root)
    labels = {
        "com.energie.component": "github-publisher",
        "com.energie.type2.binding": "canonical-v2",
    }
    if current_labels:
        labels.update({
            "com.energie.publisher.script_sha256": ident["script_sha256"],
            "com.energie.publisher.path_contract_sha256": ident["path_contract_sha256"],
        })
    return {
        "Id": "x", "Name": "/energie-github-publisher",
        "Config": {"Image": "alpine/git:2.47.2", "Labels": labels},
        "HostConfig": {"NetworkMode": "bridge", "Binds": [
            f"{root}/Inbox:/energy/Inbox:rw",
            f"{root}/Data/03_Systeem:/energy/Data/03_Systeem:rw",
            f"{root}/App/tools/system_path_contract.sh:/energy/App/tools/system_path_contract.sh:ro",
            f"{root}/App/tools/nas_github_publisher.sh:/usr/local/bin/nas_github_publisher.sh:ro",
            f"{root}/Data/03_Systeem/Projectmanager/Private/github_publisher:/publisher-private:rw",
        ]},
        "State": {"Running": True},
    }


def test_32526_publisher_binding_is_code_identity_bound(tmp_path):
    root = tmp_path / "p"
    shutil.copytree(ROOT / "tools", root / "App/tools")
    (root / "Inbox").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Private/github_publisher").mkdir(parents=True)
    assert publisher_binding.binding_current(_publisher_info(root, current_labels=True), root) is True
    stale = _publisher_info(root, current_labels=False)
    assert publisher_binding.binding_current(stale, root) is False
    payload = publisher_binding._desired_payload(stale, root)
    labels = payload["Labels"]
    assert labels["com.energie.publisher.script_sha256"] == publisher_binding._code_identity(root)["script_sha256"]
    assert labels["com.energie.publisher.path_contract_sha256"] == publisher_binding._code_identity(root)["path_contract_sha256"]


def test_32526_publisher_script_owns_processing_but_not_contract_settlement():
    text = (ROOT / "tools/nas_github_publisher.sh").read_text(encoding="utf-8")
    assert 'SOURCE_STAGE="$(json_string_field source_stage' in text
    assert '"$SOURCE_STAGE" = "processing_pre_target"' in text
    assert 'ZIP_PATH="$PROCESSING/$ZIP_NAME"' in text
    assert '"release_id":"%s","generation":"%s"' in text
    assert 'PUBLICATION_STATE=' in text
    assert 'rm -f "$CONTRACT"' not in text
    subprocess.check_call(["sh", "-n", str(ROOT / "tools/nas_github_publisher.sh")])


def test_32526_type3_inventory_is_original_five_bucket_rubric(tmp_path):
    root = tmp_path / "p"
    _w(root / "App/VERSIE.txt", "32.5.26\n")
    _j(root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json", {"status": "COMPLETE", "phase": "COMPLETE", "to_version": "32.5.26"})
    for rel in (
        "Data/03_Systeem/Projectmanager/Runtime/Locks/nas-container-cr.operation.lock",
        "Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock",
        "Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock",
        "Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_heartbeat.v2",
        "Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher.heartbeat.legacy",
        "Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json",
        "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json",
        "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json",
        "Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal/result.json",
        "Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal/result.json",
        "Data/03_Systeem/Projectmanager/Runtime/Process/process_map.json",
    ):
        _w(root / rel)
    (root / "Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup").mkdir(parents=True)
    _w(root / "Inbox/crash_recovery_cleanup_result.json")
    inv = type3.inventory_type3(root)
    assert inv["status"] == "GREEN"
    assert inv["classification"] == "TYPE3_ORIGINAL_RUBRIC"
    assert inv["item_count"] == 13
    assert inv["pending_legacy_sources"] == ["Inbox/crash_recovery_cleanup_result.json"]
    assert inv["generic_project_hygiene_is_separate"] is True
    assert "unreviewed_hygiene_debt" not in json.dumps(inv)


def test_32526_type3_apply_routes_to_final_inbox_cleanup(tmp_path):
    root = tmp_path / "p"
    _w(root / "App/VERSIE.txt", "32.5.26\n")
    _j(root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json", {"status": "COMPLETE", "phase": "COMPLETE", "to_version": "32.5.26"})
    # Missing canonical destinations keeps inventory RED, but apply still must not
    # invoke generic project housekeeping under the original Type-3 label.
    out = type3.apply_type3(root, explicit_user_text="akkoord", source="mcp_remote")
    assert out["status"] == "ROUTED_TO_FINAL_INBOX_CLEANUP"
    assert out["executed"] is False
    assert "inbox_cleanup_apply" in out["reason"]


def _load_hotfix():
    spec = importlib.util.spec_from_file_location("native_hotfix_32526", ROOT / "tools/native_mcp_runtime_contract_hotfix.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_32526_native_mcp_contains_resume_and_verified_release_artifact_export_contract():
    hotfix = _load_hotfix()
    text = hotfix.CLEARUP_EXPORT_MODULE
    for token in (
        "def release_artifact_list(", "def release_artifact_export_info(", "def release_artifact_export_chunk(",
        "def release_artifact_download_info(", "retention", "zipfile.ZipFile", "registry.json",
    ):
        assert token in text
    assert "def projectmanager_resume_context(" in hotfix.RESUME_CONTEXT_BLOCK
    assert "MANDATORY first call" in hotfix.RESUME_CONTEXT_BLOCK
    assert "CURRENT_CHAT_SWITCH_POINTER.json" in hotfix.RESUME_CONTEXT_BLOCK


def test_32527_release_identity_rc62():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.5.27"
    assert (PM / "VERSION.txt").read_text(encoding="utf-8").strip() == "2.0.0-rc62"
    contract = (ROOT / "release_test_contract.py").read_text(encoding="utf-8")
    assert 'CURRENT_RELEASE = "32.5.27"' in contract
    assert 'CURRENT_PM_VERSION = "2.0.0-rc62"' in contract


def test_32526_historical_transport_artifact_is_known_cleanup_debt():
    import root_structure_policy
    assert root_structure_policy.classify_root_entry(Path("32457_release_overlay_transport.zip")) == "development_debt"


def test_32526_quiescence_detects_writer_reappearance(tmp_path, monkeypatch):
    import release_controller_service as service
    root = tmp_path / "p"
    pubdir = root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication"
    pubdir.mkdir(parents=True)
    for key in ("github_publication_state", "github_publisher_state"):
        _activation(root, key, f"Inbox/{key}.json", f"Data/03_Systeem/Projectmanager/ReleaseController/Publication/{key}.json")
    monkeypatch.setenv("ENERGIE_PUBLICATION_WRITER_SOAK_SECONDS", "0.12")
    legacy = root / "Inbox/github_publication_state.json"
    def late_writer():
        time.sleep(0.04)
        _w(legacy, "{}\n")
    t = threading.Thread(target=late_writer, daemon=True)
    t.start()
    with pytest.raises(RuntimeError, match="legacy_publication_writer_reappeared"):
        service.verify_publication_writer_quiescence(root, _state("a"*64, "EnergieProject_v32.5.26.zip"))
    t.join(timeout=1)


def test_32526_quiescence_passes_when_legacy_writers_stay_absent(tmp_path, monkeypatch):
    import release_controller_service as service
    root = tmp_path / "p"
    pubdir = root / "Data/03_Systeem/Projectmanager/ReleaseController/Publication"
    pubdir.mkdir(parents=True)
    for key in ("github_publication_state", "github_publisher_state"):
        _activation(root, key, f"Inbox/{key}.json", f"Data/03_Systeem/Projectmanager/ReleaseController/Publication/{key}.json")
    monkeypatch.setenv("ENERGIE_PUBLICATION_WRITER_SOAK_SECONDS", "0.02")
    out = service.verify_publication_writer_quiescence(root, _state("a"*64, "EnergieProject_v32.5.26.zip"))
    assert out["status"] == "GREEN"
    assert out["legacy_source_reappearance_proof"] == "GREEN"


def test_32526_release_artifact_export_reconstructs_verified_retained_zip(tmp_path, monkeypatch):
    import types
    hotfix = _load_hotfix()
    project = tmp_path / 'project'; project.mkdir()
    system = tmp_path / 'system'; store = system / 'Projectmanager/ReleaseArtifacts'; store.mkdir(parents=True)
    artifact = store / 'EnergieProject_v32.5.25.zip'
    with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('VERSIE.txt', '32.5.25\n')
        z.writestr('payload.txt', 'predecessor')
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    _j(store/'registry.json', {
        'schema':'energie_release_artifact_registry_v1','retention':3,
        'entries':[{'name':artifact.name,'official_name':True,'size':artifact.stat().st_size,'sha256':sha}],
    })
    class MCP:
        def tool(self, annotations=None): return lambda fn: fn
    reg=types.ModuleType('registry'); reg.mcp=MCP(); reg.READ_ONLY_ANNOTATIONS={}; reg.WRITE_ANNOTATIONS={}
    old=sys.modules.get('registry'); sys.modules['registry']=reg
    monkeypatch.setenv('ENERGIE_PROJECT_ROOT',str(project)); monkeypatch.setenv('ENERGIE_SYSTEM_ROOT',str(system))
    mod=types.ModuleType('tools_clearup_export_32526')
    try:
        exec(compile(hotfix.CLEARUP_EXPORT_MODULE,'tools_clearup_export.py','exec'),mod.__dict__)
        listed=mod.release_artifact_list(); assert listed['status']=='GREEN' and listed['count']==1
        info=mod.release_artifact_export_info(); assert info['sha256']==sha and info['size']==artifact.stat().st_size
        parts=[]; offset=0
        while True:
            row=mod.release_artifact_export_chunk('',offset,17)
            parts.append(base64.b64decode(row['base64']))
            offset=row['next_offset']
            if row['eof']: break
        rebuilt=b''.join(parts)
        assert rebuilt==artifact.read_bytes()
        assert hashlib.sha256(rebuilt).hexdigest()==sha
        descriptor=mod.release_artifact_download_info()
        assert descriptor['relative_download_url'].startswith('/release-artifacts/download?')
        assert descriptor['sha256']==sha
    finally:
        if old is None: sys.modules.pop('registry',None)
        else: sys.modules['registry']=old
