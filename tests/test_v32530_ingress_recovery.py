from __future__ import annotations

import importlib
import json
import os
import time
import zipfile
from pathlib import Path

import pytest


def _tree(root: Path, live: str = "32.5.30") -> None:
    (root / "App").mkdir(parents=True, exist_ok=True)
    (root / "App/VERSIE.txt").write_text(live + "\n", encoding="utf-8")
    for rel in ("Inbox/incoming","Inbox/processing","Inbox/processed","Inbox/failed","Inbox/release_controller/Publication","Inbox/projectmanager_v2/RuntimeV2/release_ingress"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    (root / "Inbox/release_controller/current.json").write_text(json.dumps({
        "status":"COMPLETE","phase":"COMPLETE","release_id":live+":previous","generation":"a"*32,
        "from_version":"32.5.29","to_version":live,"artifact_name":f"EnergieProject_v{live}.zip",
        "artifact_sha256":"1"*64,"step":9,"total":9,
    }), encoding="utf-8")


def _candidate(path: Path, version: str) -> str:
    import hashlib
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSIE.txt", version + "\n")
        z.writestr("payload.txt", "candidate")
    old=time.time()-1200
    os.utime(path,(old,old))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _module():
    return importlib.import_module("release_ingress_recovery_executor_32530")


def test_safe_orphan_processing_requeues(tmp_path: Path):
    _tree(tmp_path)
    p=tmp_path/"Inbox/processing/EnergieProject_v32.5.31.zip"
    digest=_candidate(p,"32.5.31")
    mod=_module()
    inspection=mod.inspect(tmp_path)
    assert inspection["status"]=="RECOVERABLE"
    assert inspection["plan"]["artifact_sha256"]==digest
    result=mod.apply(tmp_path,expected_fingerprint=inspection["fingerprint"])
    assert result["status"]=="GREEN" and result["executed"] is True
    assert (tmp_path/"Inbox/incoming/EnergieProject_v32.5.31.zip").is_file()
    assert not p.exists()


def test_atomic_partial_evidence_blocks(tmp_path: Path):
    _tree(tmp_path)
    p=tmp_path/"Inbox/processing/EnergieProject_v32.5.31.zip"
    digest=_candidate(p,"32.5.31")
    (tmp_path/"Inbox/atomic_app_swap_state.json").write_text(json.dumps({
        "state":"INSTALLED","from_version":"32.5.30","to_version":"32.5.31","artifact_sha256":digest,
    }),encoding="utf-8")
    inspection=_module().inspect(tmp_path)
    assert inspection["status"]=="BLOCKED"
    assert "atomic_state_mentions_candidate" in inspection["snapshot"]["partial_evidence"]


def test_fingerprint_change_fails_closed(tmp_path: Path):
    _tree(tmp_path)
    p=tmp_path/"Inbox/processing/EnergieProject_v32.5.31.zip"
    _candidate(p,"32.5.31")
    mod=_module()
    inspection=mod.inspect(tmp_path)
    with zipfile.ZipFile(p,"a") as z:
        z.writestr("changed.txt","changed")
    with pytest.raises(mod.RecoveryRejected,match="fingerprint changed"):
        mod.apply(tmp_path,expected_fingerprint=inspection["fingerprint"])
    assert p.is_file()


def test_controller_services_recovery_before_orphan_block():
    root=Path(__file__).resolve().parents[1]
    source=(root/"tools/release_controller_service.py").read_text(encoding="utf-8")
    assert source.index("release_ingress_recovery_executor_32530.process_pending_request") < source.index("recovery=self._reconcile_idle_processing()")


def test_pm_exposes_ingress_hints():
    root=Path(__file__).resolve().parents[1]
    source=(root/"slimmemeterportal_import/rootfs/app/projectmanager_v2/command_processor.py").read_text(encoding="utf-8")
    assert "release_ingress_recovery_inspect" in source
    assert "release_ingress_recovery_recover" in source


def test_active_controller_blocks_recovery(tmp_path: Path):
    _tree(tmp_path)
    p=tmp_path/"Inbox/processing/EnergieProject_v32.5.31.zip"
    _candidate(p,"32.5.31")
    (tmp_path/"Inbox/release_controller/current.json").write_text(json.dumps({
        "status":"ACTIVE","phase":"INSTALLING","release_id":"32.5.31:owned","generation":"b"*32,
        "from_version":"32.5.30","to_version":"32.5.31","artifact_name":p.name,
        "artifact_sha256":"2"*64,"step":4,"total":9,
    }),encoding="utf-8")
    inspection=_module().inspect(tmp_path)
    assert inspection["status"]=="BLOCKED"
    assert inspection["reason"]=="release_controller_active"
