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

V64_ARTIFACT_SHA = "875939a6d2112b69cf0b6da37d6c36216c80494aec00bbd78fdf59c37ea6acce"
V64_MAIN_SHA = "ee26e4a1ff2ede372ab576f256433ceb6f2865ff042ffdecc20a09b0d80d6877"
FIXTURE = ROOT / "tests/fixtures/v64_predecessor/main.py"
V65_FIXTURE = ROOT / "tests/fixtures/v65_predecessor/main.py"


def _load_exact_v64_main():
    spec = importlib.util.spec_from_file_location("v64_exact_predecessor_main", FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
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
        from_version=from_version,
        to_version=to_version,
        artifact_sha256=sha,
        artifact_name=artifact.name,
    )
    state.phase = Phase.ACCEPTED.value
    delivery = HADelivery(root, timeout_seconds=0)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload), encoding="utf-8")
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True,
        "target_exact": True,
        "remote_head": "deadbeef",
        **{key: payload[key] for key in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256"
        )},
    }), encoding="utf-8")
    return root, state, delivery, artifact, runtime


def test_v64_predecessor_fixture_is_byte_exact_and_artifact_bound():
    assert (ROOT / "tests/fixtures/v64_predecessor/ARTIFACT_SHA256.txt").read_text().strip() == V64_ARTIFACT_SHA
    assert (ROOT / "tests/fixtures/v64_predecessor/SOURCE_SHA256.txt").read_text().strip() == V64_MAIN_SHA
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == V64_MAIN_SHA
    assert 'APP_VERSION = "32.4.64"' in FIXTURE.read_text(encoding="utf-8")


def test_exact_v64_predecessor_to_v65_refreshes_store_only(monkeypatch):
    mod = _load_exact_v64_main()
    assert mod.APP_VERSION == "32.4.64"
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=15):
        calls.append((request.full_url, request.get_method(), request.data))
        return Response()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    result = mod._request_supervisor_target_update("token", "32.4.65")
    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["store_refreshed"] is True
    assert result["manual_ha_update_required"] is True
    assert calls == [("http://supervisor/store/reload", "POST", b"{}")]
    source = FIXTURE.read_text(encoding="utf-8")
    assert "/store/addons/" not in source
    assert "/addons/self/rebuild" not in source
    assert "/addons/reload" not in source


def test_v64_to_v65_waits_then_settles_only_after_exact_manual_ha_target(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.64", "32.4.65")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.64"}), encoding="utf-8")
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()
    assert not (root / "Inbox/processed" / artifact.name).exists()

    (runtime / "current.json").write_text(json.dumps({"version": "32.4.65"}), encoding="utf-8")
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert not artifact.exists()
    assert (root / "Inbox/processed" / artifact.name).is_file()
    assert not (root / "Inbox/ha_publication_required.json").exists()


def test_v65_n_plus_one_predecessor_contract_for_synthetic_v66(monkeypatch):
    spec = importlib.util.spec_from_file_location("v65_exact_predecessor_main", V65_FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"result":"ok"}'

    def fake_urlopen(request, timeout=15):
        calls.append(request.full_url)
        return Response()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    assert mod.APP_VERSION == "32.4.65"
    result = mod._request_supervisor_target_update("token", "32.4.66")
    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert result["manual_ha_update_required"] is True
    assert calls == ["http://supervisor/store/reload"]


def test_v65_to_v66_manual_wait_and_complete_contract_is_regression_proven(tmp_path):
    root, state, delivery, artifact, runtime = _release_root(tmp_path, "32.4.65", "32.4.66")
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.65"}), encoding="utf-8")
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()

    (runtime / "current.json").write_text(json.dumps({"version": "32.4.66"}), encoding="utf-8")
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert (root / "Inbox/processed" / artifact.name).is_file()


def test_current_handover_is_single_current_authority_and_historical_59_not_embedded():
    text = (ROOT / "CURRENT_HANDOVER.md").read_text(encoding="utf-8")
    assert text.startswith("# CURRENT HANDOVER — EnergieProject 32.4.66")
    assert "# CURRENT HANDOVER — EnergieProject 32.4.59" not in text
    assert "e00a7fc0dfc81d3dfe7dbac6bac3cef213a987f207ad4d0d62588450b0bc9152" in text


def test_platform_qualification_is_explicitly_not_release_gate_and_no_test_weakening_contract():
    text = (ROOT / "PLATFORM_QUALIFICATION.md").read_text(encoding="utf-8")
    assert "geen releasegate" in text
    assert "niet verwijderd" in text
    assert "niet" in text and "verzwakt" in text
    acceptance = (ROOT / "RELEASE_ACCEPTANCE.md").read_text(encoding="utf-8")
    assert "32.4.66" in acceptance
    assert "exact V65 predecessor" in acceptance
