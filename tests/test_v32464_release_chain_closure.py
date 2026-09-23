from __future__ import annotations

import hashlib
import importlib.util
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

V63_SHA = "e0af96f555b4fef61667e17cd5c0fc81324e9edbd0257c5bc1a174e1e3b6c913"


def _load_v63_fixture():
    path = ROOT / "tests/fixtures/v63_predecessor/publisher_boundary.py"
    spec = importlib.util.spec_from_file_location("v63_predecessor_boundary", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _release_root(tmp_path: Path, from_version: str, to_version: str):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    rollback = root / f"App.__rollback_{from_version}"
    rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous", encoding="utf-8")
    (app / "VERSIE.txt").write_text(to_version, encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target", encoding="utf-8")
    artifact = processing / f"EnergieProject_v{to_version}.zip"
    artifact.write_bytes(f"artifact-{to_version}".encode())
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    state = ReleaseController().new_state(
        from_version=from_version, to_version=to_version,
        artifact_sha256=sha, artifact_name=artifact.name,
    )
    state.phase = Phase.ACCEPTED.value
    delivery = HADelivery(root, timeout_seconds=0)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True, "remote_head": "deadbeef",
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256"
        )},
    }), encoding="utf-8")
    return root, state, delivery, artifact, runtime


def test_v63_frozen_predecessor_is_bound_to_exact_live_artifact_and_refreshes_store_only(monkeypatch):
    mod = _load_v63_fixture()
    source = (ROOT / "tests/fixtures/v63_predecessor/publisher_boundary.py").read_text(encoding="utf-8")
    assert V63_SHA in source
    assert mod.APP_VERSION == "32.4.63"

    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=15):
        calls.append((request.full_url, request.get_method(), request.data))
        return Response()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    result = mod.request_target_transition("token", "32.4.64")

    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["manual_ha_update_required"] is True
    assert calls == [("http://supervisor/store/reload", "POST", b"{}")]
    assert "/store/addons/" not in source
    assert "/addons/self/rebuild" not in source
    assert "/addons/self/info" not in source


def test_63_to_64_waits_durably_in_processing_until_manual_ha_target(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.63", "32.4.64")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.63"}), encoding="utf-8")

    state.phase_started_at_epoch = 0
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()
    assert not (root / "Inbox/processed" / artifact.name).exists()
    assert (root / "Inbox/ha_publication_required.json").is_file()

    (runtime / "current.json").write_text(json.dumps({"version": "32.4.64"}), encoding="utf-8")
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert not artifact.exists()
    assert (root / "Inbox/processed" / artifact.name).is_file()
    assert not (root / "Inbox/ha_publication_required.json").exists()


def test_v64_n_plus_one_predecessor_boundary_for_synthetic_65(monkeypatch):
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=15):
        calls.append(request.full_url)
        return Response()

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(main, "APP_VERSION", "32.4.64")
    result = main._request_supervisor_target_update("token", "32.4.65")

    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["manual_ha_update_required"] is True
    assert calls == ["http://supervisor/store/reload"]


def test_v64_to_65_manual_wait_and_settlement_is_already_regression_proven(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.64", "32.4.65")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.64"}), encoding="utf-8")
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()

    (runtime / "current.json").write_text(json.dumps({"version": "32.4.65"}), encoding="utf-8")
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert (root / "Inbox/processed" / artifact.name).is_file()


def test_delivery_reconciles_crash_after_archive_before_complete_state_write(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.63", "32.4.64")
    processed = root / "Inbox/processed"
    processed.mkdir()
    dst = processed / artifact.name
    artifact.replace(dst)
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.64"}), encoding="utf-8")

    outcome = delivery.align(state)
    assert outcome.status == "GREEN"
    assert dst.is_file()
    assert not (root / "Inbox/ha_publication_required.json").exists()


def test_completed_delivery_reconciliation_is_idempotent_after_contract_cleanup(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.63", "32.4.64")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.64"}), encoding="utf-8")
    first = delivery.align(state)
    assert first.status == "GREEN"
    processed = root / "Inbox/processed" / artifact.name
    before = hashlib.sha256(processed.read_bytes()).hexdigest()

    second = delivery.reconcile_completed_delivery(state)
    after = hashlib.sha256(processed.read_bytes()).hexdigest()
    assert second.status == "GREEN"
    assert before == after
    assert list((root / "Inbox/processed").glob(artifact.name)) == [processed]


def test_active_release_core_has_single_owner_and_no_retired_auto_ha_actuators():
    main_text = (APP / "main.py").read_text(encoding="utf-8")
    core = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "tools/release_controller.py",
            "tools/release_controller_service.py",
            "tools/ha_delivery_adapter.py",
            "tools/release_watcher.sh",
        )
    )
    assert "/store/reload" in main_text
    for forbidden in ("/store/addons/", "/addons/self/rebuild", "/addons/reload"):
        assert forbidden not in main_text
    assert "release_validation_hold" not in core
    assert "release_transition" not in core
    assert "project_cr" not in core
    assert "clearup" not in core.lower()
    assert "release_controller_service.py" in (ROOT / "tools/release_watcher.sh").read_text(encoding="utf-8")


def test_processing_and_processed_semantics_are_explicit_in_delivery_code():
    text = (TOOLS / "ha_delivery_adapter.py").read_text(encoding="utf-8")
    assert "Inbox/processing" in text
    assert "Inbox/processed" in text
    assert "_archive_complete" in text
    assert "pub_exact and ha_exact" in text
    assert "WAITING_MANUAL_HA_UPDATE" in text


def test_release_acceptance_and_platform_qualification_are_distinct_contracts():
    contract = (ROOT / "AGENT_TASK.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "host-capability Platform Qualification" in changelog
    assert "release acceptance" in changelog
    assert "host-capability Platform Qualification" in contract
