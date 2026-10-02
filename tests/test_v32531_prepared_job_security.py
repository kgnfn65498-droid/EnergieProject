import hashlib
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
CP = ROOT / "tools/control_plane"
sys.path.insert(0, str(PM))
sys.path.insert(0, str(CP))

from prepared_job_service import ConfiguredPreparedJobService
import prepared_job_extension


REQ_ID = "32531a04c0ffee001122334455667788"


def _sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _fixture(tmp_path, *, operation="TEST", target="32.5.31"):
    live = "32.5.30"
    (tmp_path / "App").mkdir(parents=True)
    (tmp_path / "App/VERSIE.txt").write_text(live + "\n", encoding="utf-8")

    artifacts = tmp_path / "Data/03_Systeem/Projectmanager/ReleaseArtifacts"
    artifacts.mkdir(parents=True)
    predecessor = artifacts / f"EnergieProject_v{live}.zip"
    predecessor.write_bytes(b"retained-artifact")
    predecessor_sha = _sha(predecessor)

    job = tmp_path / f"Data/03_Systeem/Projectmanager/Staging/PreparedJobs/{REQ_ID}"
    job.mkdir(parents=True)
    runner = job / "runner.py"
    runner.write_text("print('bounded test')\n", encoding="utf-8")
    runner_sha = _sha(runner)

    task = {"id": "task-1", "mode": "DEVELOPMENT", "status": "ACTIVE"}
    manifest = {
        "schema": "energie_prepared_job_manifest_v1",
        "request_id": REQ_ID,
        "task_id": task["id"],
        "operation": operation,
        "target_release": target,
        "predecessor_release": live,
        "predecessor_sha256": predecessor_sha,
        "runner_sha256": runner_sha,
    }
    manifest_path = job / "job_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    artifact_path = runner.relative_to(tmp_path).as_posix()
    return {
        "service": ConfiguredPreparedJobService(tmp_path),
        "task": task,
        "runner": runner,
        "runner_sha": runner_sha,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "artifact_path": artifact_path,
        "predecessor_sha": predecessor_sha,
        "operation": operation,
        "target": target,
    }


def _mark_control_plane_green(tmp_path):
    runtime = tmp_path / "Inbox/control_plane/results"
    runtime.mkdir(parents=True, exist_ok=True)
    path = runtime / f"control_plane_ensure.{REQ_ID}.json"
    path.write_text(json.dumps({
        "schema": "energie_control_plane_ensure_result_v1",
        "request_id": REQ_ID,
        "status": "GREEN",
        "ok": True,
        "target": "energie-control-plane",
        "production_modified": False,
    }), encoding="utf-8")
    return path


def test_prepared_job_derives_identity_from_existing_submit_fields(tmp_path):
    fx = _fixture(tmp_path)
    result = fx["service"].run(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    assert result["status"] == "PENDING"
    assert result["awaiting_control_plane"] is True
    assert result["awaiting_executor"] is False
    assert result["request_id"] == REQ_ID
    assert result["predecessor_release"] == "32.5.30"
    assert result["predecessor_sha256"] == fx["predecessor_sha"]

    runtime = tmp_path / "Inbox/control_plane"
    ensure_request = json.loads((runtime / f"requests/control_plane_ensure.{REQ_ID}.json").read_text())
    assert ensure_request == {
        "schema": "energie_control_plane_ensure_request_v1",
        "request_id": REQ_ID,
        "action": "ensure_running",
        "target": "energie-control-plane",
    }
    assert not (runtime / f"authorizations/prepared_job_run.{REQ_ID}.json").exists()
    assert not (runtime / f"requests/prepared_job_run.{REQ_ID}.json").exists()

    _mark_control_plane_green(tmp_path)
    result = fx["service"].run(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    assert result["awaiting_executor"] is True
    auth = json.loads((runtime / f"authorizations/prepared_job_run.{REQ_ID}.json").read_text())
    request = json.loads((runtime / f"requests/prepared_job_run.{REQ_ID}.json").read_text())
    assert auth["task_id"] == fx["task"]["id"]
    assert request["runner_sha256"] == fx["runner_sha"]
    assert request["manifest_sha256"] == _sha(fx["manifest_path"])
    assert (runtime / f"authorizations/prepared_job_run.{REQ_ID}.json").stat().st_mode & 0o777 == 0o644
    assert (runtime / f"requests/prepared_job_run.{REQ_ID}.json").stat().st_mode & 0o777 == 0o644


def test_prepared_job_is_idempotent_while_authorization_is_live(tmp_path):
    fx = _fixture(tmp_path)
    kwargs = dict(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    first = fx["service"].run(**kwargs)
    assert first["awaiting_control_plane"] is True
    _mark_control_plane_green(tmp_path)
    first = fx["service"].run(**kwargs)
    auth_path = tmp_path / f"Inbox/control_plane/authorizations/prepared_job_run.{REQ_ID}.json"
    auth_before = auth_path.read_bytes()
    second = fx["service"].run(**kwargs)
    assert second["authorization_sha256"] == first["authorization_sha256"]
    assert auth_path.read_bytes() == auth_before


def test_prepared_job_rejects_wrong_runner_or_manifest_identity(tmp_path):
    fx = _fixture(tmp_path)
    with pytest.raises(RuntimeError, match="runner identity mismatch"):
        fx["service"].run(
            task=fx["task"],
            artifact_path=fx["artifact_path"],
            artifact_sha256="0" * 64,
            target_release=fx["target"],
            operation=fx["operation"],
        )

    fx = _fixture(tmp_path / "manifest")
    payload = json.loads(fx["manifest_path"].read_text())
    payload["target_release"] = "32.5.99"
    fx["manifest_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest identity mismatch"):
        fx["service"].run(
            task=fx["task"],
            artifact_path=fx["artifact_path"],
            artifact_sha256=fx["runner_sha"],
            target_release=fx["target"],
            operation=fx["operation"],
        )


def test_prepared_job_rejects_expired_unclaimed_authorization(tmp_path):
    fx = _fixture(tmp_path)
    kwargs = dict(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    first = fx["service"].run(**kwargs)
    assert first["awaiting_control_plane"] is True
    _mark_control_plane_green(tmp_path)
    fx["service"].run(**kwargs)
    auth_path = tmp_path / f"Inbox/control_plane/authorizations/prepared_job_run.{REQ_ID}.json"
    auth = json.loads(auth_path.read_text())
    auth["expires_at_epoch"] = time.time() - 1
    auth.pop("authorization_sha256", None)
    canonical = json.dumps(auth, sort_keys=True, separators=(",", ":")).encode()
    auth["authorization_sha256"] = hashlib.sha256(canonical).hexdigest()
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    with pytest.raises(RuntimeError, match="authorization expired"):
        fx["service"].run(**kwargs)


def test_control_plane_claim_is_binding_checked_and_single_use(tmp_path):
    fx = _fixture(tmp_path)
    first = fx["service"].run(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    assert first["awaiting_control_plane"] is True
    _mark_control_plane_green(tmp_path)
    result = fx["service"].run(
        task=fx["task"],
        artifact_path=fx["artifact_path"],
        artifact_sha256=fx["runner_sha"],
        target_release=fx["target"],
        operation=fx["operation"],
    )
    runtime = tmp_path / "Inbox/control_plane"
    request = json.loads((runtime / f"requests/prepared_job_run.{REQ_ID}.json").read_text())

    cp = SimpleNamespace(result_root=runtime)
    claimed = prepared_job_extension._claim_authorization(cp, request)
    assert claimed["authorization_sha256"] == result["authorization_sha256"]
    assert not (runtime / f"authorizations/prepared_job_run.{REQ_ID}.json").exists()
    assert (runtime / f"claims/prepared_job_run.{REQ_ID}.json").is_file()
    assert (runtime / f"claims/prepared_job_run.{REQ_ID}.json").stat().st_mode & 0o777 == 0o600

    again = prepared_job_extension._claim_authorization(cp, request)
    assert again == claimed

    tampered = dict(request)
    tampered["task_id"] = "other-task"
    with pytest.raises(RuntimeError, match="binding mismatch"):
        prepared_job_extension._claim_authorization(cp, tampered)
