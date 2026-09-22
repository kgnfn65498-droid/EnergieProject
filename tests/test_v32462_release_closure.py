from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
TOOLS = ROOT / "tools"
for value in (str(APP), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)

import main
from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController


def _contract62() -> dict:
    return {
        "version": "32.4.62",
        "repository": "https://github.com/kgnfn65498-droid/EnergieProject",
        "branch": "main",
        "expected_previous_version": "32.4.61",
        "expected_previous_manifest_sha256": "previous-manifest",
        "target_manifest_sha256": "target-manifest",
        "processed_zip": "EnergieProject_v32.4.62.zip",
        "processed_zip_sha256": "b" * 64,
        "release_id": "32.4.62:" + "b" * 12,
        "generation": "1234567890abcdef1234567890abcdef",
    }


def test_61_predecessor_can_publish_62_and_request_target_update(monkeypatch, tmp_path):
    """The active N publisher, not N+1 code, must cross the pre-target boundary."""
    contract = _contract62()
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "VERSIE.txt").write_text("32.4.62", encoding="utf-8")
    (stage / "MANIFEST.sha256").write_text("target", encoding="utf-8")

    monkeypatch.setattr(main, "APP_VERSION", "32.4.61")
    monkeypatch.setattr(main, "github_publication_status", lambda options=None: {
        "key_ready": True, "repository": "git@github.com:kgnfn65498-droid/EnergieProject.git"
    })
    monkeypatch.setattr(main, "_load_github_publication_contract", lambda options=None: (True, contract, "ok"))
    monkeypatch.setattr(main, "_prepare_github_worktree", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(main, "_prepare_validated_publication_source", lambda c: (True, stage, "ok"))
    monkeypatch.setattr(main, "_classify_github_remote_baseline", lambda *args, **kwargs: (True, "target_exact", "ok"))
    updates = []
    monkeypatch.setattr(main, "_request_supervisor_target_update", lambda token, target: updates.append(target) or {
        "status": "GREEN", "requested": True, "target_version": target
    })
    written = []
    monkeypatch.setattr(main, "_write_github_publish_state", lambda payload: written.append(dict(payload)))

    result = main.publish_github_release({
        "github_publication_enabled": True,
        "github_repository_ssh": "git@github.com:kgnfn65498-droid/EnergieProject.git",
        "github_branch": "main",
    })

    assert updates == ["32.4.62"]
    assert result["published"] is True and result["target_exact"] is True
    assert result["release_id"] == contract["release_id"]
    assert written[-1]["published"] is True and written[-1]["target_exact"] is True


def test_61_predecessor_delivery_failure_cannot_erase_62_publication(monkeypatch, tmp_path):
    contract = _contract62()
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "VERSIE.txt").write_text("32.4.62", encoding="utf-8")
    (stage / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    monkeypatch.setattr(main, "APP_VERSION", "32.4.61")
    monkeypatch.setattr(main, "github_publication_status", lambda options=None: {"key_ready": True, "repository": "x"})
    monkeypatch.setattr(main, "_load_github_publication_contract", lambda options=None: (True, contract, "ok"))
    monkeypatch.setattr(main, "_prepare_github_worktree", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(main, "_prepare_validated_publication_source", lambda c: (True, stage, "ok"))
    monkeypatch.setattr(main, "_classify_github_remote_baseline", lambda *args, **kwargs: (True, "target_exact", "ok"))
    monkeypatch.setattr(main, "_request_supervisor_target_update", lambda *args, **kwargs: {
        "status": "RED", "requested": False, "failed_endpoint": "/store/addons/x/update", "error": "HTTP 400"
    })
    monkeypatch.setattr(main, "_write_github_publish_state", lambda payload: None)
    result = main.publish_github_release({"github_publication_enabled": True, "github_repository_ssh": "x", "github_branch": "main"})
    assert result["published"] is True
    assert result["target_exact"] is True
    assert result["ha_delivery"]["status"] == "RED"


def test_62_processing_archives_only_after_exact_ha_runtime(tmp_path):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    rollback = root / "App.__rollback_32.4.61"
    rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous", encoding="utf-8")
    (app / "VERSIE.txt").write_text("32.4.62", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    artifact = processing / "EnergieProject_v32.4.62.zip"
    artifact.write_bytes(b"artifact62")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    controller = ReleaseController()
    state = controller.new_state(from_version="32.4.61", to_version="32.4.62", artifact_sha256=sha, artifact_name=artifact.name)
    state.phase = Phase.ACCEPTED.value
    state.phase_started_at_epoch = 10**12  # force waiting, never timeout in test
    delivery = HADelivery(root)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True, "remote_head": "deadbeef",
        **{k: payload[k] for k in ("version", "release_id", "generation", "processed_zip", "processed_zip_sha256", "target_manifest_sha256")},
    }), encoding="utf-8")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.61"}), encoding="utf-8")

    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert artifact.is_file()
    assert not (inbox / "processed" / artifact.name).exists()

    (runtime / "current.json").write_text(json.dumps({"version": "32.4.62"}), encoding="utf-8")
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert not artifact.exists()
    assert (inbox / "processed" / artifact.name).is_file()
    assert not (inbox / "ha_publication_required.json").exists()
