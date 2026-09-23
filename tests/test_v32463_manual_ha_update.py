from __future__ import annotations

import hashlib
import io
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


def test_predecessor_publisher_only_refreshes_store_after_github_target(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=15):
        calls.append((request.full_url, request.get_method(), request.data))
        return Response()

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(main, "APP_VERSION", "32.4.62")

    result = main._request_supervisor_target_update("token", "32.4.63")

    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["store_refreshed"] is True
    assert result["manual_ha_update_required"] is True
    assert [url for url, _method, _data in calls] == ["http://supervisor/store/reload"]


def test_exact_github_with_predecessor_ha_runtime_waits_without_timeout(tmp_path):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    rollback = root / "App.__rollback_32.4.62"
    rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous", encoding="utf-8")
    (app / "VERSIE.txt").write_text("32.4.63", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    artifact = processing / "EnergieProject_v32.4.63.zip"
    artifact.write_bytes(b"artifact63")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    state = ReleaseController().new_state(
        from_version="32.4.62", to_version="32.4.63", artifact_sha256=sha, artifact_name=artifact.name
    )
    state.phase = Phase.ACCEPTED.value
    state.phase_started_at_epoch = 0
    delivery = HADelivery(root, timeout_seconds=0)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True, "remote_head": "deadbeef",
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip", "processed_zip_sha256", "target_manifest_sha256"
        )},
    }), encoding="utf-8")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.62"}), encoding="utf-8")

    outcome = delivery.align(state)

    assert outcome.status == "WAITING"
    assert outcome.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()
    assert not (inbox / "processed" / artifact.name).exists()


def test_exact_target_runtime_settles_manual_wait_and_archives_processing(tmp_path):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    rollback = root / "App.__rollback_32.4.62"
    rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous", encoding="utf-8")
    (app / "VERSIE.txt").write_text("32.4.63", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    artifact = processing / "EnergieProject_v32.4.63.zip"
    artifact.write_bytes(b"artifact63")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    state = ReleaseController().new_state(
        from_version="32.4.62", to_version="32.4.63", artifact_sha256=sha, artifact_name=artifact.name
    )
    state.phase = Phase.ACCEPTED.value
    delivery = HADelivery(root)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True, "remote_head": "deadbeef",
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip", "processed_zip_sha256", "target_manifest_sha256"
        )},
    }), encoding="utf-8")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.63"}), encoding="utf-8")

    outcome = delivery.align(state)

    assert outcome.status == "GREEN"
    assert not artifact.exists()
    assert (inbox / "processed" / artifact.name).is_file()
    assert not (inbox / "ha_publication_required.json").exists()
