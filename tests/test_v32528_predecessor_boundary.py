from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
for value in (str(TOOLS), str(APP)):
    if value not in sys.path:
        sys.path.insert(0, value)

from ha_delivery_adapter import HADelivery
from release_controller import Outcome, Phase
from release_controller_service import ReleaseControllerService
from system_path_contract import MAPPINGS, SCHEMA, project_system_path

PREDECESSOR_RELEASE_SHA256 = "ea3674ebc32067a7c71b5798f33cb3e9de03f1d1c178dcb96e0f73e7dc4e89f2"
PREDECESSOR_MODULE_SHA256 = {
    "tools/release_controller.py": "d2fa9065e4124c1468674544f4a3bf7a0d0ea04366bcfea9753d084c87330331",
    "tools/release_controller_service.py": "7f82cc7a20f3e42efa33802f3f4b10f91ac12b920cbc929c178432dddfdf5529",
    "tools/ha_delivery_adapter.py": "b9548d5088b5385c926ede62e4782567aae8fd7e628ef5b919f9c2182974f4d2",
    "tools/release_runtime_adapter.py": "c3483df9d4b7f8b761d71b2714c855c93efa5290e9883b1808da138cdadca1be",
    "tools/atomic_release_adapter.py": "17545120830bc19ab219f14878ab21a9c8016c6c35d95fc76c380a42870d2228",
    "tools/minimal_release_preflight.py": "8ec039ef6087f7745c3e084b0adaa3ba3a198084e502cb68d49099cba9515aff",
    "tools/ingress_policy.py": "f32dbb6a435c0a0eaa71814ec7fdbde6a7423f52abde61e7b863e60788eee8cd",
    "tools/nas_github_publisher.sh": "52fb61313b321c3d7fafe6a961bd9d111bc329874e78776bb0e0ba8b8f605f4e",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")



def _activate_mapping(root: Path, key: str) -> None:
    source, destination = MAPPINGS[key]
    dest = root / destination
    if key in {"github_publication_state", "github_publisher_state"}:
        dest.parent.mkdir(parents=True, exist_ok=True)
    else:
        dest.mkdir(parents=True, exist_ok=True)
    marker = root / "Data/03_Systeem/Projectmanager/ClearUp/PathActivation" / f"{key}.json"
    _write_json(marker, {"schema": SCHEMA, "key": key, "source": source, "destination": destination, "active": True})


def _candidate(path: Path, version: str = "32.5.28") -> str:
    payload = {
        "VERSIE.txt": (version + "\n").encode(),
        "payload.txt": b"predecessor-boundary-proof\n",
    }
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    manifest_text = "".join(f"{sha}  {name}\n" for name, sha in sorted(manifest.items()))
    sums = {"files": [{"path": name, "sha256": sha} for name, sha in sorted(manifest.items())]}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in payload.items():
            z.writestr(name, data)
        z.writestr("MANIFEST.sha256", manifest_text.encode())
        z.writestr("SHA256SUMS.json", (json.dumps(sums, sort_keys=True) + "\n").encode())
    return _sha(path)


class _FenceAdapter:
    def pre_target_publication(self, state):
        return Outcome.waiting("publisher_event_not_simulated_yet")

    def install(self, state):
        return Outcome.green("not_used")

    def runtime_align(self, state):
        return Outcome.green("not_used")

    def verify_live(self, state):
        return Outcome.green("not_used")

    def atomic_accept(self, state):
        return Outcome.green("not_used")

    def delivery(self, state):
        return Outcome.waiting("not_used")

    def rollback(self, state, reason):
        return Outcome.rolled_back(reason)


def _predecessor_zip() -> Path:
    raw = os.environ.get("ENERGIE_PREDECESSOR_ZIP", "").strip()
    if not raw:
        import pytest
        pytest.skip("exact 32.5.27 predecessor ZIP is required for predecessor-boundary acceptance")
    path = Path(raw).resolve()
    assert path.is_file() and not path.is_symlink()
    assert _sha(path) == PREDECESSOR_RELEASE_SHA256
    return path


def test_32528_predecessor_release_path_modules_are_exact_32527_bytes():
    predecessor = _predecessor_zip()
    with zipfile.ZipFile(predecessor) as archive:
        for rel, expected in PREDECESSOR_MODULE_SHA256.items():
            assert hashlib.sha256(archive.read(rel)).hexdigest() == expected, rel


def test_32527_predecessor_claims_32528_from_incoming_and_delivery_archives_only_after_ha_exact(tmp_path):
    root = tmp_path / "p"
    for rel in ("Inbox/incoming", "Inbox/processing", "Inbox/processed", "Inbox/failed"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for key in ("release_controller", "ha_runtime", "github_publication_state", "github_publisher_state"):
        _activate_mapping(root, key)

    app = root / "App"
    app.mkdir(parents=True)
    (app / "VERSIE.txt").write_text("32.5.27\n", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("live-32527\n", encoding="utf-8")

    candidate = root / "Inbox/incoming/EnergieProject_v32.5.28.zip"
    artifact_sha = _candidate(candidate)

    # Exact predecessor ReleaseControllerService owns the only Incoming -> Processing move.
    service = ReleaseControllerService(root, _FenceAdapter(), stable_polls=1, ingress_stale_seconds=600)
    first = service.cycle()
    assert first is None
    state = service.cycle()
    assert state is not None
    assert state.from_version == "32.5.27"
    assert state.to_version == "32.5.28"
    assert state.artifact_sha256 == artifact_sha
    assert state.phase == Phase.PUBLISHING.value
    processing = root / "Inbox/processing/EnergieProject_v32.5.28.zip"
    assert not candidate.exists()
    assert processing.is_file()
    assert _sha(processing) == artifact_sha

    # Simulate accepted App state and canonical publisher event; never write legacy Inbox publication state.
    rollback = root / "App.__rollback_32.5.27"
    rollback.mkdir(parents=True)
    (rollback / "MANIFEST.sha256").write_text("live-32527\n", encoding="utf-8")
    (app / "VERSIE.txt").write_text("32.5.28\n", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("target-32528\n", encoding="utf-8")

    state.phase = Phase.ACCEPTED.value
    delivery = HADelivery(root, timeout_seconds=0)
    contract = delivery._contract(state, processing)
    _write_json(root / "Inbox/release_controller/Publication/ha_publication_required.json", contract)
    publication = Path(project_system_path(root, "Inbox/github_publication_state.json"))
    _write_json(publication, {
        "published": True,
        "target_exact": True,
        "remote_head": "deadbeef",
        "local_head": "deadbeef",
        **{key: contract[key] for key in (
            "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_manifest_sha256",
        )},
    })
    assert not (root / "Inbox/github_publication_state.json").exists()
    assert not (root / "Inbox/github_publisher_state.json").exists()

    ha_runtime = Path(project_system_path(root, "Inbox/ha_runtime/current.json"))
    _write_json(ha_runtime, {"version": "32.5.27"})
    waiting = delivery.align(state)
    assert waiting.status == "WAITING"
    assert waiting.reason == "WAITING_MANUAL_HA_UPDATE"
    assert processing.is_file()
    assert not (root / "Inbox/processed/EnergieProject_v32.5.28.zip").exists()

    _write_json(ha_runtime, {"version": "32.5.28"})
    green = delivery.align(state)
    assert green.status == "GREEN"
    processed = root / "Inbox/processed/EnergieProject_v32.5.28.zip"
    assert processed.is_file()
    assert _sha(processed) == artifact_sha
    assert not processing.exists()
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())
