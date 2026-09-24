from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from release_test_contract import CURRENT_RELEASE

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
TOOLS = ROOT / "tools"
for value in (str(APP), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)

import main
from ha_delivery_adapter import HADelivery
from release_controller import Phase, ReleaseController

V65_ARTIFACT_SHA = "e00a7fc0dfc81d3dfe7dbac6bac3cef213a987f207ad4d0d62588450b0bc9152"
V65_MAIN_SHA = "35814b8555f2d50078ba9fcb77324b76a635530ce31f79cd1585b63463df018c"
FIXTURE = ROOT / "tests/fixtures/v65_predecessor/main.py"
PROVENANCE = ROOT / "tests/fixtures/v65_predecessor/PROVENANCE.json"


def _load_v65():
    spec = importlib.util.spec_from_file_location("v65_exact_predecessor_for_v66", FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _root(tmp_path: Path, predecessor="32.4.65", target="32.4.66"):
    inbox=tmp_path/"Inbox"; processing=inbox/"processing"; runtime=inbox/"ha_runtime"
    processing.mkdir(parents=True); runtime.mkdir()
    app=tmp_path/"App"; app.mkdir()
    rollback=tmp_path/f"App.__rollback_{predecessor}"; rollback.mkdir()
    (rollback/"MANIFEST.sha256").write_text("previous")
    (app/"VERSIE.txt").write_text(target)
    (app/"MANIFEST.sha256").write_text("target")
    artifact=processing/f"EnergieProject_v{target}.zip"; artifact.write_bytes(f"artifact-{target}".encode())
    sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
    state=ReleaseController().new_state(from_version=predecessor,to_version=target,artifact_sha256=sha,artifact_name=artifact.name)
    state.phase=Phase.ACCEPTED.value
    delivery=HADelivery(tmp_path,timeout_seconds=0)
    payload=delivery._contract(state,artifact)
    (inbox/"ha_publication_required.json").write_text(json.dumps(payload))
    pub={"published":True,"target_exact":True,"remote_head":"deadbeef","publication_contract_removed":False,
         "publication_contract_settled":False,"publication_contract_active":True,"contract_settled_by":None,
         **{k:payload[k] for k in ("version","release_id","generation","processed_zip","processed_zip_sha256","target_manifest_sha256")}}
    (inbox/"github_publication_state.json").write_text(json.dumps(pub))
    return state,delivery,artifact,runtime,inbox,payload


def test_v65_fixture_is_exact_and_provenance_bound():
    meta=json.loads(PROVENANCE.read_text())
    assert meta["artifact_sha256"] == V65_ARTIFACT_SHA
    assert meta["source_sha256"] == V65_MAIN_SHA
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == V65_MAIN_SHA
    assert 'APP_VERSION = "32.4.65"' in FIXTURE.read_text()


def test_exact_v65_predecessor_to_v66_refreshes_store_only(monkeypatch):
    mod=_load_v65(); calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"result":"ok"}'
    def fake(request,timeout=15): calls.append(request.full_url); return Response()
    monkeypatch.setattr(mod.urllib.request,"urlopen",fake)
    result=mod._request_supervisor_target_update("token","32.4.66")
    assert result["status"] == "GREEN"
    assert result["requested"] is False
    assert calls == ["http://supervisor/store/reload"]
    source=FIXTURE.read_text()
    assert "/store/addons/" not in source and "/addons/self/rebuild" not in source and "/addons/reload" not in source


def test_controller_settlement_updates_shared_publication_observability(tmp_path):
    state,delivery,artifact,runtime,inbox,payload=_root(tmp_path)
    (runtime/"current.json").write_text(json.dumps({"version":"32.4.66"}))
    out=delivery.align(state)
    assert out.status == "GREEN"
    pub=json.loads((inbox/"github_publication_state.json").read_text())
    assert pub["publication_contract_removed"] is True
    assert pub["publication_contract_settled"] is True
    assert pub["publication_contract_active"] is False
    assert pub["contract_settled_by"] == "release_controller"
    assert pub["settled_release_id"] == state.release_id
    assert pub["settled_generation"] == state.generation
    assert not (inbox/"ha_publication_required.json").exists()
    assert (inbox/"processed"/artifact.name).is_file()


def test_manual_wait_does_not_prematurely_mark_contract_settled(tmp_path):
    state,delivery,artifact,runtime,inbox,payload=_root(tmp_path)
    (runtime/"current.json").write_text(json.dumps({"version":"32.4.65"}))
    out=delivery.align(state)
    assert out.status == "WAITING" and out.reason == "WAITING_MANUAL_HA_UPDATE"
    pub=json.loads((inbox/"github_publication_state.json").read_text())
    assert pub["publication_contract_removed"] is False
    assert pub["publication_contract_settled"] is False
    assert pub["publication_contract_active"] is True
    assert artifact.is_file()


def test_static_handover_has_no_mutable_live_status_claim():
    text=(ROOT/"CURRENT_HANDOVER.md").read_text()
    assert text.startswith(f"# CURRENT HANDOVER — EnergieProject {CURRENT_RELEASE}")
    assert "Status: DEVELOPMENT" not in text
    assert "Status: WAITING" not in text
    assert "Status: COMPLETE" not in text
    assert "runtime-statusautoriteit" in text.lower()
    assert "Inbox/release_controller/current.json" in text


def test_v66_to_synthetic_v67_keeps_manual_ha_boundary(monkeypatch):
    # Historical V66 predecessor proof must execute frozen V66 code, never the
    # mutable current target release module.
    fixture=ROOT/"tests/fixtures/v66_predecessor/main.py"
    spec=importlib.util.spec_from_file_location("v66_historical_predecessor",fixture)
    mod=importlib.util.module_from_spec(spec); assert spec and spec.loader
    sys.modules[spec.name]=mod; spec.loader.exec_module(mod)
    calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b'{"result":"ok"}'
    def fake(request,timeout=15): calls.append(request.full_url); return Response()
    monkeypatch.setattr(mod.urllib.request,"urlopen",fake)
    assert mod.APP_VERSION == "32.4.66"
    result=mod._request_supervisor_target_update("token","32.4.67")
    assert result["status"] == "GREEN" and result["requested"] is False
    assert calls == ["http://supervisor/store/reload"]
