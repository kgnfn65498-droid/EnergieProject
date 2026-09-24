from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for path in (str(TOOLS), str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController, Status
from release_controller_service import write_post_live_audit
from projectmanager_v2.release_health import release_health_checks
from projectmanager_v2.energy_health_collector import EnergyHealthCollector
import main


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jwrite(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def candidate(path: Path, version: str = "32.5.5") -> tuple[str, str]:
    manifest = hashlib.sha256(version.encode()).hexdigest() + "  VERSIE.txt\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("VERSIE.txt", version)
        archive.writestr("MANIFEST.sha256", manifest)
    return sha(path), hashlib.sha256(manifest.encode()).hexdigest()


def split_state(tmp_path: Path):
    app = tmp_path / "App"
    app.mkdir()
    (app / "VERSIE.txt").write_text("32.5.2", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("local-52", encoding="utf-8")
    local_manifest = sha(app / "MANIFEST.sha256")

    processing = tmp_path / "Inbox/processing"
    processing.mkdir(parents=True)
    artifact = processing / "EnergieProject_v32.5.5.zip"
    artifact_sha, target_manifest = candidate(artifact)

    remote_manifest = "5" * 64
    jwrite(tmp_path / "Inbox/github_publication_state.json", {
        "published": True,
        "target_exact": True,
        "version": "32.5.3",
        "target_manifest_sha256": remote_manifest,
        "remote_head": "abc123",
        "local_head": "abc123",
    })
    jwrite(tmp_path / "Inbox/ha_runtime/current.json", {"version": "32.5.3"})

    state = ReleaseController().new_state(
        from_version="32.5.2",
        to_version="32.5.5",
        artifact_sha256=artifact_sha,
        artifact_name=artifact.name,
    )
    state.phase = Phase.PUBLISHING.value
    return state, artifact, local_manifest, remote_manifest, target_manifest


def test_split_state_contract_keeps_install_and_publication_predecessors_separate(tmp_path):
    state, artifact, local_manifest, remote_manifest, _ = split_state(tmp_path)
    delivery = HADelivery(tmp_path)
    contract = delivery._pre_target_contract(state, artifact)
    assert contract["install_predecessor_version"] == "32.5.2"
    assert contract["install_predecessor_manifest_sha256"] == local_manifest
    assert contract["publication_predecessor_version"] == "32.5.3"
    assert contract["publication_predecessor_manifest_sha256"] == remote_manifest
    assert contract["expected_previous_version"] == "32.5.3"
    assert contract["predecessor_version"] == "32.5.3"


def test_split_state_recovery_publishes_then_installs_without_contract_recompute_conflict(tmp_path):
    state, artifact, _, _, _ = split_state(tmp_path)
    delivery = HADelivery(tmp_path, timeout_seconds=0.01)

    first = delivery.prepare_pre_target(state)
    assert first.status == "WAITING"
    assert "split_state_recovery_active" in first.evidence
    contract_path = tmp_path / "Inbox/ha_publication_required.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    # Canonical publisher advances target while local App is still the accepted
    # installation predecessor. This is the exact 32.5.3/32.5.4 incident shape.
    jwrite(tmp_path / "Inbox/github_publication_state.json", {
        "published": True,
        "target_exact": True,
        "version": state.to_version,
        "release_id": state.release_id,
        "generation": state.generation,
        "processed_zip": state.artifact_name,
        "processed_zip_sha256": state.artifact_sha256,
        "target_manifest_sha256": contract["target_manifest_sha256"],
        "remote_head": "target-head",
        "local_head": "target-head",
    })
    assert delivery.prepare_pre_target(state).status == "GREEN"

    rollback = tmp_path / "App.__rollback_32.5.2"
    (tmp_path / "App").rename(rollback)
    app = tmp_path / "App"
    app.mkdir()
    (app / "VERSIE.txt").write_text(state.to_version, encoding="utf-8")
    with zipfile.ZipFile(artifact) as archive:
        (app / "MANIFEST.sha256").write_bytes(archive.read("MANIFEST.sha256"))

    state.phase = Phase.ACCEPTED.value
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert contract_path.exists()

    jwrite(tmp_path / "Inbox/ha_runtime/current.json", {"version": state.to_version})
    settled = delivery.align(state)
    assert settled.status == "GREEN"
    assert not contract_path.exists()
    assert not artifact.exists()
    assert (tmp_path / "Inbox/processed" / state.artifact_name).is_file()


def test_publisher_accepts_dual_domain_split_state_without_impersonating_local_version(tmp_path, monkeypatch):
    live = tmp_path / "App"
    live.mkdir()
    (live / "VERSIE.txt").write_text("32.5.2", encoding="utf-8")
    (live / "MANIFEST.sha256").write_text("local", encoding="utf-8")
    install_manifest = sha(live / "MANIFEST.sha256")
    release_root = tmp_path / "Inbox"
    processing = release_root / "processing"
    processed = release_root / "processed"
    processing.mkdir(parents=True)
    processed.mkdir()
    artifact = processing / "EnergieProject_v32.5.5.zip"
    artifact_sha, target_manifest = candidate(artifact)
    publication_manifest = "a" * 64
    contract = {
        "schema": "energie_ha_publication_contract_v2",
        "status": "publication_required",
        "source_stage": "processing_pre_target",
        "version": "32.5.5",
        "repository": "https://github.com/kgnfn65498-droid/EnergieProject",
        "branch": "main",
        "install_predecessor_version": "32.5.2",
        "install_predecessor_manifest_sha256": install_manifest,
        "publication_predecessor_version": "32.5.3",
        "publication_predecessor_manifest_sha256": publication_manifest,
        "expected_previous_version": "32.5.3",
        "expected_previous_manifest_sha256": publication_manifest,
        "predecessor_version": "32.5.3",
        "predecessor_manifest_sha256": publication_manifest,
        "target_manifest_sha256": target_manifest,
        "processed_zip": artifact.name,
        "processed_zip_sha256": artifact_sha,
        "release_id": "32.5.5:" + artifact_sha[:12],
        "generation": "0123456789abcdef0123456789abcdef",
    }
    marker = release_root / "ha_publication_required.json"
    jwrite(marker, contract)
    jwrite(release_root / "release_controller/current.json", {
        "release_id": contract["release_id"],
        "generation": contract["generation"],
        "to_version": contract["version"],
        "artifact_sha256": artifact_sha,
        "phase": "PUBLISHING",
        "status": "WAITING",
    })
    canonical = release_root / "github_publication_state.json"
    jwrite(canonical, {
        "published": True,
        "target_exact": True,
        "version": "32.5.3",
        "target_manifest_sha256": publication_manifest,
        "remote_head": "pred-head",
        "local_head": "pred-head",
    })
    jwrite(release_root / "ha_runtime/current.json", {"version": "32.5.3"})

    monkeypatch.setattr(main, "NAS_PROJECT_ROOT", live)
    monkeypatch.setattr(main, "NAS_RELEASE_ROOT", release_root)
    monkeypatch.setattr(main, "NAS_RELEASE_PROCESSING", processing)
    monkeypatch.setattr(main, "NAS_RELEASE_ARCHIVE", processed)
    monkeypatch.setattr(main, "HA_PUBLICATION_REQUIRED", marker)
    monkeypatch.setattr(main, "GITHUB_CANONICAL_PUBLISH_STATE", canonical)
    monkeypatch.setattr(main, "GITHUB_RELEASE_STAGE", tmp_path / "stage")

    ok, loaded, message = main._load_github_publication_contract()
    assert ok is True, message
    assert loaded["processed_path"] == str(artifact)
    assert (live / "VERSIE.txt").read_text(encoding="utf-8") == "32.5.2"


def test_publisher_rejects_dual_domain_when_ha_and_canonical_remote_disagree(tmp_path, monkeypatch):
    # Start from the valid split-state fixture above by constructing the minimum
    # dual-domain contract, then break only HA runtime identity.
    live = tmp_path / "App"; live.mkdir()
    (live / "VERSIE.txt").write_text("32.5.2")
    (live / "MANIFEST.sha256").write_text("local")
    release_root = tmp_path / "Inbox"; processing = release_root / "processing"; processing.mkdir(parents=True)
    artifact = processing / "EnergieProject_v32.5.5.zip"; artifact_sha, target_manifest = candidate(artifact)
    publication_manifest = "b" * 64
    contract = {
        "status":"publication_required","source_stage":"processing_pre_target","version":"32.5.5",
        "repository":"https://github.com/kgnfn65498-droid/EnergieProject","branch":"main",
        "install_predecessor_version":"32.5.2","install_predecessor_manifest_sha256":sha(live/"MANIFEST.sha256"),
        "publication_predecessor_version":"32.5.3","publication_predecessor_manifest_sha256":publication_manifest,
        "expected_previous_version":"32.5.3","expected_previous_manifest_sha256":publication_manifest,
        "predecessor_version":"32.5.3","predecessor_manifest_sha256":publication_manifest,
        "target_manifest_sha256":target_manifest,"processed_zip":artifact.name,"processed_zip_sha256":artifact_sha,
        "release_id":"32.5.5:"+artifact_sha[:12],"generation":"fedcba9876543210fedcba9876543210",
    }
    marker=release_root/"ha_publication_required.json"; jwrite(marker,contract)
    jwrite(release_root/"release_controller/current.json",{"release_id":contract["release_id"],"generation":contract["generation"],"to_version":"32.5.5","artifact_sha256":artifact_sha,"phase":"PUBLISHING","status":"WAITING"})
    canonical=release_root/"github_publication_state.json";jwrite(canonical,{"published":True,"target_exact":True,"version":"32.5.3","target_manifest_sha256":publication_manifest,"remote_head":"h","local_head":"h"})
    jwrite(release_root/"ha_runtime/current.json",{"version":"32.5.2"})
    monkeypatch.setattr(main,"NAS_PROJECT_ROOT",live);monkeypatch.setattr(main,"NAS_RELEASE_ROOT",release_root)
    monkeypatch.setattr(main,"NAS_RELEASE_PROCESSING",processing);monkeypatch.setattr(main,"NAS_RELEASE_ARCHIVE",release_root/"processed")
    monkeypatch.setattr(main,"HA_PUBLICATION_REQUIRED",marker);monkeypatch.setattr(main,"GITHUB_CANONICAL_PUBLISH_STATE",canonical)
    ok,_,message=main._load_github_publication_contract()
    assert ok is False
    assert "HA-runtime" in message


def test_complete_release_writes_machine_readable_green_post_live_audit(tmp_path):
    app=tmp_path/"App";app.mkdir();(app/"VERSIE.txt").write_text("32.5.5")
    processed=tmp_path/"Inbox/processed";processed.mkdir(parents=True)
    artifact=processed/"EnergieProject_v32.5.5.zip";artifact.write_bytes(b"artifact")
    artifact_sha=sha(artifact)
    state=ReleaseController().new_state(from_version="32.5.4",to_version="32.5.5",artifact_sha256=artifact_sha,artifact_name=artifact.name)
    state.phase=Phase.COMPLETE.value;state.status=Status.COMPLETE.value;state.step=9;state.total=9
    jwrite(tmp_path/"Inbox/ha_runtime/current.json",{"version":"32.5.5"})
    jwrite(tmp_path/"Inbox/atomic_app_swap_state.json",{"state":"ACCEPTED","to_version":"32.5.5","artifact_sha256":artifact_sha})
    jwrite(tmp_path/"Inbox/github_publication_state.json",{
        "published":True,"target_exact":True,"version":"32.5.5","release_id":state.release_id,"generation":state.generation,
        "processed_zip_sha256":artifact_sha,"remote_head":"head","local_head":"head",
        "publication_contract_settled":True,"publication_contract_active":False,"contract_settled_by":"release_controller",
    })
    audit=write_post_live_audit(tmp_path,state)
    assert audit["status"]=="GREEN"
    assert all(audit["checks"].values())
    saved=json.loads((tmp_path/"Inbox/release_controller/post_live_audit.json").read_text())
    assert saved["recommendation"]=="release_closed_next_development_safe"


def test_release_health_accepts_settled_idle_controller_as_green():
    runtime={"release":{"version":"32.5.5"},"release_chain":{"release_controller":{"active":False,"phase":"COMPLETE","status":"COMPLETE"}}}
    checks={c["name"]:c for c in release_health_checks(runtime)}
    assert checks["release_controller_liveness"]["status"]=="GREEN"
    assert checks["release_controller_liveness"]["reason"]=="controller_idle_settled"


def test_energy_health_does_not_mark_old_idle_runtime_red_after_complete(tmp_path):
    project=tmp_path/"project";inputs=tmp_path/"input";recovery=tmp_path/"recovery"
    (project/"App").mkdir(parents=True);(project/"App/VERSIE.txt").write_text("32.5.5")
    runtime=project/"Inbox/release_controller/runtime.json"
    jwrite(runtime,{"schema":"energie_release_controller_runtime_v1","pid":1,"phase":"IDLE","status":"IDLE"})
    jwrite(project/"Inbox/release_controller/current.json",{"phase":"COMPLETE","status":"COMPLETE","to_version":"32.5.5"})
    old=time.time()-3600;os.utime(runtime,(old,old))
    checks=EnergyHealthCollector(project,inputs,recovery).collect(now=datetime.now(timezone.utc))
    item=next(c for c in checks if c["name"]=="release_controller_runtime")
    assert item["status"]=="GREEN"
    assert item["reason"]=="controller_idle_settled"
