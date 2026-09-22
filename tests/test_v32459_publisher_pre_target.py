from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import main

TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from release_controller import Outcome, Phase, ReleaseController
from ha_delivery_adapter import HADelivery


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(path: Path) -> tuple[str, str]:
    version = "32.4.60"
    version_bytes = version.encode("utf-8")
    manifest = hashlib.sha256(version_bytes).hexdigest() + "  VERSIE.txt\n"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("VERSIE.txt", version_bytes)
        archive.writestr("MANIFEST.sha256", manifest)
    return _sha(path), hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def _pre_target_contract(name: str, artifact_sha: str, target_manifest_sha: str, previous_manifest_sha: str) -> dict:
    return {
        "schema": "energie_ha_publication_contract_v2",
        "status": "publication_required",
        "source_stage": "processing_pre_target",
        "version": "32.4.60",
        "repository": "https://github.com/kgnfn65498-droid/EnergieProject",
        "branch": "main",
        "expected_previous_version": "32.4.59",
        "expected_previous_manifest_sha256": previous_manifest_sha,
        "predecessor_version": "32.4.59",
        "predecessor_manifest_sha256": previous_manifest_sha,
        "target_manifest_sha256": target_manifest_sha,
        "processed_zip": name,
        "processed_zip_sha256": artifact_sha,
        "release_id": "32.4.60:" + artifact_sha[:12],
        "generation": "0123456789abcdef0123456789abcdef",
    }


def _configure(tmp_path: Path):
    inbox = tmp_path / "Inbox"
    processing = inbox / "processing"
    processed = inbox / "processed"
    processing.mkdir(parents=True)
    processed.mkdir()
    live = tmp_path / "App"
    live.mkdir()
    (live / "VERSIE.txt").write_text("32.4.59", encoding="utf-8")
    (live / "MANIFEST.sha256").write_text("previous-manifest", encoding="utf-8")
    candidate = processing / "EnergieProject_v32.4.60.zip"
    artifact_sha, target_manifest_sha = _candidate(candidate)
    marker = inbox / "ha_publication_required.json"
    contract = _pre_target_contract(candidate.name, artifact_sha, target_manifest_sha, _sha(live / "MANIFEST.sha256"))
    marker.write_text(json.dumps(contract), encoding="utf-8")
    current = inbox / "release_controller/current.json"
    current.parent.mkdir()
    current.write_text(json.dumps({
        "release_id": contract["release_id"], "generation": contract["generation"],
        "to_version": contract["version"], "artifact_sha256": contract["processed_zip_sha256"],
        "phase": "PUBLISHING", "status": "ACTIVE",
    }), encoding="utf-8")
    stage = tmp_path / "stage"
    return live, processing, processed, marker, stage


def _with_paths(live: Path, processing: Path, processed: Path, marker: Path, stage: Path):
    original = {
        "NAS_PROJECT_ROOT": main.NAS_PROJECT_ROOT,
        "NAS_RELEASE_ROOT": main.NAS_RELEASE_ROOT,
        "NAS_RELEASE_PROCESSING": main.NAS_RELEASE_PROCESSING,
        "NAS_RELEASE_ARCHIVE": main.NAS_RELEASE_ARCHIVE,
        "HA_PUBLICATION_REQUIRED": main.HA_PUBLICATION_REQUIRED,
        "GITHUB_RELEASE_STAGE": main.GITHUB_RELEASE_STAGE,
    }
    main.NAS_PROJECT_ROOT = live
    main.NAS_RELEASE_ROOT = marker.parent
    main.NAS_RELEASE_PROCESSING = processing
    main.NAS_RELEASE_ARCHIVE = processed
    main.HA_PUBLICATION_REQUIRED = marker
    main.GITHUB_RELEASE_STAGE = stage
    return original


def _restore_paths(original: dict) -> None:
    for name, value in original.items():
        setattr(main, name, value)


def test_pre_target_processing_candidate_is_accepted_only_with_exact_identity(tmp_path):
    live, processing, processed, marker, stage = _configure(tmp_path)
    original = _with_paths(live, processing, processed, marker, stage)
    try:
        ok, _, message = main._load_github_publication_contract()
    finally:
        _restore_paths(original)
    assert ok is True, message


def test_pre_target_contract_rejects_missing_identity_and_stale_or_foreign_predecessor(tmp_path):
    live, processing, processed, marker, stage = _configure(tmp_path)
    original = _with_paths(live, processing, processed, marker, stage)
    try:
        contract = json.loads(marker.read_text(encoding="utf-8"))
        for field, value in (
            ("release_id", ""),
            ("generation", ""),
            ("predecessor_version", "32.4.58"),
            ("predecessor_manifest_sha256", "foreign"),
            ("processed_zip_sha256", "0" * 64),
            ("target_manifest_sha256", "f" * 64),
        ):
            candidate = dict(contract)
            candidate[field] = value
            marker.write_text(json.dumps(candidate), encoding="utf-8")
            ok, loaded, _ = main._load_github_publication_contract()
            if field == "target_manifest_sha256" and ok:
                ready, _, _ = main._prepare_validated_publication_source(loaded)
                assert ready is False, field
            else:
                assert ok is False, field
    finally:
        _restore_paths(original)


def test_pre_target_publisher_keeps_contract_and_processing_ownership(tmp_path):
    live, processing, processed, marker, stage = _configure(tmp_path)
    original = _with_paths(live, processing, processed, marker, stage)
    try:
        ok, contract, message = main._load_github_publication_contract()
        assert ok is True, message
        ready, source, message = main._prepare_validated_publication_source(contract)
        assert ready is True, message
        assert source is not None
        assert marker.exists()
        assert (processing / contract["processed_zip"]).is_file()
        assert not (processed / contract["processed_zip"]).exists()
    finally:
        _restore_paths(original)


def test_controller_waits_for_exact_pre_target_publication_before_installation():
    class Adapter:
        def __init__(self):
            self.pre_target_calls = 0
            self.install_calls = 0

        def pre_target_publication(self, state):
            self.pre_target_calls += 1
            return Outcome.waiting("github_pre_target_pending")

        def install(self, state):
            self.install_calls += 1
            return Outcome.green("install")

    controller = ReleaseController()
    state = controller.new_state(
        from_version="32.4.59", to_version="32.4.60",
        artifact_sha256="a" * 64, artifact_name="EnergieProject_v32.4.60.zip",
    )
    controller.mark_verified(state, ["candidate_verified"])
    adapter = Adapter()
    controller.cycle(state, adapter)
    assert state.phase == Phase.PUBLISHING.value
    controller.cycle(state, adapter)
    assert state.status == "WAITING"
    assert adapter.pre_target_calls == 1
    assert adapter.install_calls == 0


def test_pre_target_contract_requires_matching_active_controller_identity(tmp_path):
    live, processing, processed, marker, stage = _configure(tmp_path)
    original = _with_paths(live, processing, processed, marker, stage)
    try:
        contract = json.loads(marker.read_text(encoding="utf-8"))
        current = marker.parent / "release_controller/current.json"
        current.parent.mkdir(exist_ok=True)
        current.write_text(json.dumps({
            "release_id": contract["release_id"], "generation": contract["generation"],
            "to_version": contract["version"], "artifact_sha256": contract["processed_zip_sha256"],
            "phase": "PUBLISHING", "status": "ACTIVE",
        }), encoding="utf-8")
        ok, _, message = main._load_github_publication_contract()
        assert ok is True, message
        current.write_text(json.dumps({**json.loads(current.read_text(encoding="utf-8")), "generation": "foreign"}), encoding="utf-8")
        ok, _, _ = main._load_github_publication_contract()
        assert ok is False
        current.write_text(json.dumps({
            "release_id": contract["release_id"], "generation": contract["generation"],
            "to_version": contract["version"], "artifact_sha256": contract["processed_zip_sha256"],
            "phase": "COMPLETE", "status": "COMPLETE",
        }), encoding="utf-8")
        ok, _, _ = main._load_github_publication_contract()
        assert ok is False
    finally:
        _restore_paths(original)


def test_controller_owned_pre_target_contract_settles_only_after_target_runtime(tmp_path):
    root = tmp_path
    inbox = root / "Inbox"
    processing = inbox / "processing"
    runtime = inbox / "ha_runtime"
    processing.mkdir(parents=True)
    runtime.mkdir()
    app = root / "App"
    app.mkdir()
    (app / "VERSIE.txt").write_text("32.4.59", encoding="utf-8")
    (app / "MANIFEST.sha256").write_text("previous-manifest", encoding="utf-8")
    artifact = processing / "EnergieProject_v32.4.60.zip"
    artifact_sha, _ = _candidate(artifact)
    controller = ReleaseController()
    state = controller.new_state(from_version="32.4.59", to_version="32.4.60", artifact_sha256=artifact_sha, artifact_name=artifact.name)
    state.phase = Phase.PUBLISHING.value
    delivery = HADelivery(root)
    assert delivery.prepare_pre_target(state).status == "WAITING"
    contract = json.loads((inbox / "ha_publication_required.json").read_text(encoding="utf-8"))
    (inbox / "github_publication_state.json").write_text(json.dumps({
        "published": True, "target_exact": True, "remote_head": "deadbeef",
        **{key: contract[key] for key in ("version", "release_id", "generation", "processed_zip", "processed_zip_sha256", "target_manifest_sha256")},
    }), encoding="utf-8")
    assert delivery.prepare_pre_target(state).status == "GREEN"
    rollback = root / "App.__rollback_32.4.59"
    app.rename(rollback)
    app.mkdir()
    (app / "VERSIE.txt").write_text("32.4.60", encoding="utf-8")
    with zipfile.ZipFile(artifact) as archive:
        (app / "MANIFEST.sha256").write_bytes(archive.read("MANIFEST.sha256"))
    runtime.joinpath("current.json").write_text(json.dumps({"version": "32.4.60"}), encoding="utf-8")
    state.phase = Phase.ACCEPTED.value
    assert delivery.align(state).status == "GREEN"
    assert not (inbox / "ha_publication_required.json").exists()
    assert not artifact.exists()
    assert (inbox / "processed" / artifact.name).is_file()
