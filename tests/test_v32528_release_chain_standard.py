from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
for value in (str(TOOLS), str(APP)):
    if value not in sys.path:
        sys.path.insert(0, value)

from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController
from release_controller_service import ReleaseControllerService
from system_path_contract import project_system_path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _round(root: Path, from_version: str, to_version: str) -> None:
    inbox = root / "Inbox"
    (inbox / "incoming").mkdir(parents=True, exist_ok=True)
    (inbox / "processing").mkdir(parents=True, exist_ok=True)
    (inbox / "processed").mkdir(parents=True, exist_ok=True)

    app = root / "App"
    app.mkdir(parents=True, exist_ok=True)
    (app / "VERSIE.txt").write_text(to_version + "\n", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target-" + to_version, encoding="utf-8")
    rollback = root / f"App.__rollback_{from_version}"
    rollback.mkdir(parents=True, exist_ok=True)
    (rollback / "MANIFEST.sha256").write_text("previous-" + from_version, encoding="utf-8")

    name = f"EnergieProject_v{to_version}.zip"
    incoming = inbox / "incoming" / name
    incoming.write_bytes(("artifact-" + to_version).encode("utf-8"))
    sha = hashlib.sha256(incoming.read_bytes()).hexdigest()

    service = ReleaseControllerService(root, adapter=None)
    state = ReleaseController().new_state(
        from_version=from_version,
        to_version=to_version,
        artifact_sha256=sha,
        artifact_name=name,
    )
    ReleaseController().mark_verified(state, ["test_verified"])
    assert service._claim(state) is True
    processing = inbox / "processing" / name
    assert not incoming.exists()
    assert processing.is_file()
    assert hashlib.sha256(processing.read_bytes()).hexdigest() == sha

    state.phase = Phase.ACCEPTED.value
    delivery = HADelivery(root, timeout_seconds=0)
    payload = delivery._contract(state, processing)
    _write_json(inbox / "ha_publication_required.json", payload)
    publication = Path(project_system_path(root, "Inbox/github_publication_state.json"))
    _write_json(publication, {
        "published": True,
        "target_exact": True,
        "remote_head": "deadbeef",
        "local_head": "deadbeef",
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256",
        )},
    })
    ha_runtime = Path(project_system_path(root, "Inbox/ha_runtime/current.json"))
    _write_json(ha_runtime, {"version": from_version})

    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert processing.is_file()
    assert not (inbox / "processed" / name).exists()

    _write_json(ha_runtime, {"version": to_version})
    green = delivery.align(state)
    assert green.status == "GREEN"
    processed = inbox / "processed" / name
    assert processed.is_file()
    assert hashlib.sha256(processed.read_bytes()).hexdigest() == sha
    assert not processing.exists()
    assert (inbox / "processing").is_dir()
    assert not any((inbox / "processing").iterdir())


def test_32528_two_consecutive_releases_reuse_processing_and_archive_only_after_ha(tmp_path):
    root = tmp_path / "p"
    _round(root, "32.5.27", "32.5.28")
    _round(root, "32.5.28", "32.5.29")


def test_32528_agent_task_binds_release_chain_and_handover_freshness():
    text = (ROOT / "AGENT_TASK.md").read_text(encoding="utf-8")
    assert "Incoming → Processing → HA → Processed" in text
    assert "twee opeenvolgende releases" in text
    assert "host-capability Platform Qualification" in text
    assert "always-current handover" in text
