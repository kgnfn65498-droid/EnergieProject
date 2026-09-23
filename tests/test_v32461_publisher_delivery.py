from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import main

TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController


def _contract() -> dict:
    return {
        "version": "32.4.61",
        "repository": "https://github.com/kgnfn65498-droid/EnergieProject",
        "branch": "main",
        "expected_previous_version": "32.4.60",
        "expected_previous_manifest_sha256": "prev-manifest",
        "target_manifest_sha256": "target-manifest",
        "processed_zip": "EnergieProject_v32.4.61.zip",
        "processed_zip_sha256": "a" * 64,
        "release_id": "32.4.61:" + "a" * 12,
        "generation": "0123456789abcdef0123456789abcdef",
    }


def test_target_exact_keeps_publication_green_when_ha_delivery_is_red(monkeypatch, tmp_path):
    contract = _contract()
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "VERSIE.txt").write_text("32.4.61", encoding="utf-8")
    (stage / "MANIFEST.sha256").write_text("x", encoding="utf-8")

    monkeypatch.setattr(main, "github_publication_status", lambda options=None: {
        "key_ready": True, "repository": "git@github.com:kgnfn65498-droid/EnergieProject.git"
    })
    monkeypatch.setattr(main, "_load_github_publication_contract", lambda options=None: (True, contract, "ok"))
    monkeypatch.setattr(main, "_prepare_github_worktree", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(main, "_prepare_validated_publication_source", lambda c: (True, stage, "ok"))
    monkeypatch.setattr(main, "_classify_github_remote_baseline", lambda *args, **kwargs: (True, "target_exact", "ok"))
    monkeypatch.setattr(main, "_request_supervisor_target_update", lambda *args, **kwargs: {
        "status": "RED", "requested": False, "failed_endpoint": "/store/addons/test/update", "error": "HTTP 400"
    })
    written = []
    monkeypatch.setattr(main, "_write_github_publish_state", lambda payload: written.append(dict(payload)))

    result = main.publish_github_release({
        "github_publication_enabled": True,
        "github_repository_ssh": "git@github.com:kgnfn65498-droid/EnergieProject.git",
        "github_branch": "main",
    })

    assert result["published"] is True
    assert result["target_exact"] is True
    assert result["release_id"] == contract["release_id"]
    assert result["generation"] == contract["generation"]
    assert result["processed_zip_sha256"] == contract["processed_zip_sha256"]
    assert result["target_manifest_sha256"] == contract["target_manifest_sha256"]
    assert result["ha_delivery"]["status"] == "RED"
    assert written and written[-1]["published"] is True
    assert written[-1]["target_exact"] is True


def test_supervisor_target_update_refreshes_store_only_and_requires_manual_update(monkeypatch):
    calls = []

    class Response:
        def __init__(self, body: str):
            self._body = body.encode()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self._body

    def fake_urlopen(request, timeout=15):
        calls.append((request.full_url, request.get_method(), request.data))
        return Response(json.dumps({"result": "ok", "data": {}}))

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(main, "APP_VERSION", "32.4.64")
    result = main._request_supervisor_target_update("token", "32.4.65")

    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["store_refreshed"] is True
    assert result["manual_ha_update_required"] is True
    assert [url for url, _method, _data in calls] == ["http://supervisor/store/reload"]


def test_supervisor_target_update_reports_store_reload_failure_exactly(monkeypatch):
    def fake_urlopen(request, timeout=15):
        raise RuntimeError("reload failed")

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(main, "APP_VERSION", "32.4.64")
    result = main._request_supervisor_target_update("token", "32.4.65")

    assert result["status"] == "RED"
    assert result["requested"] is False
    assert result["failed_endpoint"] == "/store/reload"
    assert result["error"] == "RuntimeError: reload failed"


def test_supervisor_target_update_skips_when_running_target(monkeypatch):
    monkeypatch.setattr(main, "APP_VERSION", "32.4.65")
    result = main._request_supervisor_target_update("token", "32.4.65")
    assert result == {"status": "ALREADY_TARGET", "requested": False, "target_version": "32.4.65"}


def test_delivery_settles_on_exact_github_and_exact_ha_even_with_ha_delivery_red(tmp_path):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    rollback = root / "App.__rollback_32.4.60"
    rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous", encoding="utf-8")
    (app / "VERSIE.txt").write_text("32.4.61", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    artifact = processing / "EnergieProject_v32.4.61.zip"
    artifact.write_bytes(b"artifact")

    import hashlib
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    controller = ReleaseController()
    state = controller.new_state(
        from_version="32.4.60", to_version="32.4.61", artifact_sha256=sha, artifact_name=artifact.name
    )
    state.phase = Phase.ACCEPTED.value
    state.phase_started_at_epoch = 0
    delivery = HADelivery(root)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True,
        "target_exact": True,
        "remote_head": "deadbeef",
        "ha_delivery": {"status": "RED", "error": "HTTP 400"},
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256"
        )},
    }), encoding="utf-8")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.61"}), encoding="utf-8")

    outcome = delivery.align(state)
    assert outcome.status == "GREEN"
    assert not artifact.exists()
    assert (inbox / "processed" / artifact.name).is_file()
    assert not (inbox / "ha_publication_required.json").exists()


def test_native_successor_controller_has_nine_phases_and_enters_publishing_first():
    controller = ReleaseController()
    state = controller.new_state(
        from_version="32.4.60", to_version="32.4.61",
        artifact_sha256="a" * 64, artifact_name="EnergieProject_v32.4.61.zip",
    )
    controller.mark_verified(state, ["candidate_verified"])
    assert state.total == 9
    controller.cycle(state, object())
    assert state.phase == "PUBLISHING"
    assert state.step == 3
