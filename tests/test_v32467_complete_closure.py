from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
TOOLS = ROOT / "tools"
for value in (str(APP), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)

import main
from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController, Status
from release_controller_service import ReleaseControllerService
from projectmanager_v2.runtime_sources import RuntimeCollector

V66_ARTIFACT_SHA = "507ab36206578351621089c4c430caeb386b2005dbb637c9a9c8cfdeaa57107b"
FIX = ROOT / "tests/fixtures/v66_predecessor"
PROV = FIX / "PROVENANCE.json"
EXPECTED = {
    "main.py": "7c6990d0904cfa61b0643fb5be5825f493959d94f4c4a8a87762fefabfdd1767",
    "ha_delivery_adapter.py": "bde1980ceebffc2cd78faf1e9fc16cb669508a5def9173ecfb0c6ce94a65d4fb",
    "release_controller.py": "d2fa9065e4124c1468674544f4a3bf7a0d0ea04366bcfea9753d084c87330331",
    "release_controller_service.py": "b8fc0f1533fc6c2d32b6d7e060cc0d58fdb3423ab13040977c2dc841733d6f21",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_v66_main():
    return _load("v66_exact_main_for_v67", FIX / "main.py")


def _load_v66_release_components():
    old = sys.modules.get("release_controller")
    rc = _load("release_controller", FIX / "release_controller.py")
    adapter = _load("v66_exact_adapter_for_v67", FIX / "ha_delivery_adapter.py")
    if old is not None:
        sys.modules["release_controller"] = old
    else:
        sys.modules.pop("release_controller", None)
    return rc, adapter


def _make_zip(path: Path, manifest=b"target-manifest\n") -> str:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.sha256", manifest)
        z.writestr("payload.txt", b"payload")
    return _sha(path)


def _completed_root(tmp_path: Path, *, target="32.4.67"):
    inbox = tmp_path / "Inbox"
    processed = inbox / "processed"
    runtime = inbox / "ha_runtime"
    controller_dir = inbox / "release_controller"
    processed.mkdir(parents=True)
    runtime.mkdir()
    controller_dir.mkdir()
    app = tmp_path / "App"
    app.mkdir()
    (app / "VERSIE.txt").write_text(target)
    artifact = processed / f"EnergieProject_v{target}.zip"
    artifact_sha = _make_zip(artifact)
    state = ReleaseController().new_state(
        from_version="32.4.66", to_version=target,
        artifact_sha256=artifact_sha, artifact_name=artifact.name,
    )
    state.phase = Phase.COMPLETE.value
    state.status = Status.COMPLETE.value
    state.step = 9
    state.evidence = [
        "github_target_exact", "ha_runtime_current",
        "publication_contract_settled", "processed_archived",
    ]
    (runtime / "current.json").write_text(json.dumps({"version": target}))
    target_manifest_sha = hashlib.sha256(
        zipfile.ZipFile(artifact).read("MANIFEST.sha256")
    ).hexdigest()
    pub = {
        "published": True, "target_exact": True,
        "remote_head": "abc123", "local_head": "abc123",
        "version": target, "release_id": state.release_id,
        "generation": state.generation,
        "processed_zip": artifact.name,
        "processed_zip_sha256": artifact_sha,
        "target_manifest_sha256": target_manifest_sha,
        "publication_contract_removed": False,
    }
    pub_path = inbox / "github_publication_state.json"
    pub_path.write_text(json.dumps(pub, sort_keys=True))
    (controller_dir / "current.json").write_text(json.dumps(state.to_dict()))
    return state, artifact, pub_path


def test_v66_predecessor_fixture_is_byte_exact_and_bound():
    meta = json.loads(PROV.read_text())
    assert meta["artifact_sha256"] == V66_ARTIFACT_SHA
    assert meta["files"] == EXPECTED
    for name, digest in EXPECTED.items():
        assert _sha(FIX / name) == digest


def test_exact_v66_predecessor_publisher_to_v67_uses_store_reload_only(monkeypatch):
    mod = _load_v66_main()
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"result":"ok"}'
    def fake(request, timeout=15):
        calls.append(request.full_url)
        return Response()
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)
    assert mod.APP_VERSION == "32.4.66"
    result = mod._request_supervisor_target_update("token", "32.4.67")
    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert calls == ["http://supervisor/store/reload"]


def test_exact_v66_executor_settles_66_to_67_before_v67_reexec(tmp_path):
    rc, v66_adapter = _load_v66_release_components()
    inbox = tmp_path / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True); runtime.mkdir()
    app = tmp_path / "App"; app.mkdir()
    rollback = tmp_path / "App.__rollback_32.4.66"; rollback.mkdir()
    (rollback / "MANIFEST.sha256").write_text("previous")
    (app / "VERSIE.txt").write_text("32.4.67")
    (app / "MANIFEST.sha256").write_text("target")
    artifact = processing / "EnergieProject_v32.4.67.zip"
    artifact.write_bytes(b"v67-artifact")
    sha = _sha(artifact)
    state = rc.ReleaseController().new_state(
        from_version="32.4.66", to_version="32.4.67",
        artifact_sha256=sha, artifact_name=artifact.name,
    )
    state.phase = rc.Phase.ACCEPTED.value
    delivery = v66_adapter.HADelivery(tmp_path, timeout_seconds=0)
    payload = delivery._contract(state, artifact)
    (inbox / "ha_publication_required.json").write_text(json.dumps(payload))
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True,
        "remote_head": "head", "local_head": "head",
        "publication_contract_removed": False,
        "publication_contract_settled": False,
        "publication_contract_active": True,
        "contract_settled_by": None,
        **{k: payload[k] for k in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256")},
    }))
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.66"}))
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert artifact.is_file()
    (runtime / "current.json").write_text(json.dumps({"version": "32.4.67"}))
    green = delivery.align(state)
    assert green.status == "GREEN"
    assert not artifact.exists()
    assert (inbox / "processed" / artifact.name).is_file()
    pub = json.loads((inbox / "github_publication_state.json").read_text())
    assert pub["publication_contract_settled"] is True
    assert pub["publication_contract_removed"] is True
    assert pub["publication_contract_active"] is False
    assert pub["contract_settled_by"] == "release_controller"
    assert pub["settled_release_id"] == state.release_id
    assert pub["settled_generation"] == state.generation


def test_v67_complete_missing_marker_backfills_and_is_idempotent(tmp_path):
    state, artifact, pub_path = _completed_root(tmp_path)
    delivery = HADelivery(tmp_path)
    before_artifact = _sha(artifact)
    out = delivery.reconcile_completed_delivery(state)
    assert out.status == "GREEN"
    first = pub_path.read_bytes()
    pub = json.loads(first)
    assert pub["publication_contract_settled"] is True
    assert pub["publication_contract_active"] is False
    assert pub["contract_settled_by"] == "release_controller"
    assert pub["settled_release_id"] == state.release_id
    assert pub["settled_generation"] == state.generation
    assert _sha(artifact) == before_artifact
    out2 = delivery.reconcile_completed_delivery(state)
    assert out2.status == "GREEN"
    assert pub_path.read_bytes() == first
    assert _sha(artifact) == before_artifact


def test_v67_service_reconciles_complete_even_without_marker(tmp_path):
    state, artifact, pub_path = _completed_root(tmp_path)
    calls = []
    class Adapter:
        def reconcile_completed_delivery(self, s):
            calls.append(s.release_id)
            from release_controller import Outcome
            return Outcome.green("ok")
    service = ReleaseControllerService(tmp_path, Adapter(), stable_polls=2)
    service.store.save(state.to_dict())
    service.cycle()
    assert calls == [state.release_id]


def test_v67_fail_closed_matrix_for_completed_backfill(tmp_path):
    mutators = {
        "wrong_release_id": lambda state, pub, root: pub.__setitem__("release_id", "foreign"),
        "wrong_generation": lambda state, pub, root: pub.__setitem__("generation", "foreign"),
        "wrong_version": lambda state, pub, root: pub.__setitem__("version", "32.4.99"),
        "wrong_processed_zip": lambda state, pub, root: pub.__setitem__("processed_zip", "foreign.zip"),
        "wrong_artifact_sha": lambda state, pub, root: pub.__setitem__("processed_zip_sha256", "0"*64),
        "wrong_manifest": lambda state, pub, root: pub.__setitem__("target_manifest_sha256", "1"*64),
        "head_mismatch": lambda state, pub, root: pub.__setitem__("local_head", "other"),
        "published_false": lambda state, pub, root: pub.__setitem__("published", False),
        "target_not_exact": lambda state, pub, root: pub.__setitem__("target_exact", False),
        "ha_predecessor": lambda state, pub, root: (root/"Inbox/ha_runtime/current.json").write_text(json.dumps({"version":"32.4.66"})),
        "app_mismatch": lambda state, pub, root: (root/"App/VERSIE.txt").write_text("32.4.66"),
        "evidence_incomplete": lambda state, pub, root: setattr(state, "evidence", ["github_target_exact"]),
    }
    for name, mutate in mutators.items():
        case = tmp_path / name
        state, artifact, pub_path = _completed_root(case)
        pub = json.loads(pub_path.read_text())
        mutate(state, pub, case)
        pub_path.write_text(json.dumps(pub, sort_keys=True))
        before_pub = pub_path.read_bytes()
        before_artifact = _sha(artifact)
        out = HADelivery(case).reconcile_completed_delivery(state)
        assert out.status == "BLOCKED", name
        assert pub_path.read_bytes() == before_pub, name
        assert _sha(artifact) == before_artifact, name


def test_v67_foreign_contract_blocks_backfill(tmp_path):
    state, artifact, pub_path = _completed_root(tmp_path)
    marker = tmp_path / "Inbox/ha_publication_required.json"
    marker.write_text(json.dumps({
        "version": state.to_version, "release_id": "foreign", "generation": state.generation,
        "processed_zip": state.artifact_name, "processed_zip_sha256": state.artifact_sha256,
        "target_manifest_sha256": json.loads(pub_path.read_text())["target_manifest_sha256"],
    }))
    before = pub_path.read_bytes()
    out = HADelivery(tmp_path).reconcile_completed_delivery(state)
    assert out.status == "BLOCKED"
    assert pub_path.read_bytes() == before
    assert artifact.is_file()


def test_runtime_sources_rejects_stale_explicit_settlement_identity(tmp_path):
    inbox = tmp_path / "Inbox"
    (inbox / "release_controller").mkdir(parents=True)
    (tmp_path / "App").mkdir()
    (tmp_path / "App/VERSIE.txt").write_text("32.4.67")
    current = {
        "status":"COMPLETE","phase":"COMPLETE","to_version":"32.4.67",
        "release_id":"67:exact","generation":"gen67",
    }
    (inbox / "release_controller/current.json").write_text(json.dumps(current))
    (inbox / "release_controller/runtime.json").write_text(json.dumps({"status":"IDLE","phase":"IDLE","pid":1}))
    pub = {
        "published":True,"remote_head":"h","local_head":"h","version":"32.4.67",
        "publication_contract_settled":True,"publication_contract_removed":True,
        "contract_settled_by":"release_controller","settled_release_id":"foreign",
        "settled_generation":"gen67",
    }
    (inbox / "github_publication_state.json").write_text(json.dumps(pub))
    out = RuntimeCollector(tmp_path, running_release_version="32.4.67")._release_chain(now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    assert out["github_publication"]["settlement_identity_exact"] is False
    assert out["github_publication"]["status"] == "error"


def test_v67_to_synthetic_v68_keeps_manual_ha_boundary(monkeypatch):
    calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"result":"ok"}'
    def fake(request,timeout=15): calls.append(request.full_url); return Response()
    monkeypatch.setattr(main.urllib.request,"urlopen",fake)
    assert main.APP_VERSION == "32.4.67"
    result=main._request_supervisor_target_update("token","32.4.68")
    assert result["status"] == "GREEN" and result["requested"] is False
    assert calls == ["http://supervisor/store/reload"]
