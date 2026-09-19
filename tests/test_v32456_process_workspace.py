import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _root(tmp_path: Path) -> Path:
    (tmp_path / "App").mkdir()
    (tmp_path / "Backups").mkdir()
    (tmp_path / "Inbox").mkdir()
    (tmp_path / "Data").mkdir()
    (tmp_path / "Infra").mkdir()
    return tmp_path


def test_process_workspace_creates_canonical_layout_and_shared_map(tmp_path):
    from process_workspace import ensure_process_workspace

    root = _root(tmp_path)
    result = ensure_process_workspace(root)

    process = root / "Inbox/process"
    assert result["root"] == "Inbox/process"
    assert process.is_dir()
    assert (process / "tmp").is_dir()
    assert (process / "cache").is_dir()
    assert (process / "active").is_dir()

    process_map = process / "process_map.json"
    payload = json.loads(process_map.read_text(encoding="utf-8"))
    assert payload["schema"] == "energie_process_workspace_v1"
    assert payload["entries"] == {}
    assert payload["allowed_namespaces"] == ["tmp", "cache", "active"]
    assert process_map.stat().st_mode & 0o777 == 0o666


def test_process_workspace_rejects_artifact_outside_canonical_tree(tmp_path):
    from process_workspace import register_process_artifact

    root = _root(tmp_path)
    outside = root / "loose.tmp"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="Inbox/process"):
        register_process_artifact(
            root,
            outside,
            owner="test",
            purpose="must-not-escape",
            kind="tmp",
        )


def test_released_registered_artifact_is_clearup_candidate_but_active_is_not(tmp_path):
    from process_workspace import (
        clearup_process_candidates,
        register_process_artifact,
        release_process_artifact,
    )

    root = _root(tmp_path)
    active = root / "Inbox/process/tmp/active-job"
    released = root / "Inbox/process/cache/released-cache"
    active.mkdir(parents=True)
    released.mkdir(parents=True)
    (active / "data.txt").write_text("active", encoding="utf-8")
    (released / "data.txt").write_text("released", encoding="utf-8")

    now = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    register_process_artifact(root, active, owner="pytest", purpose="active", kind="tmp", now=now)
    register_process_artifact(root, released, owner="pytest", purpose="cache", kind="cache", now=now)
    release_process_artifact(root, released, now=now + timedelta(seconds=1))

    candidates = clearup_process_candidates(root, now=now + timedelta(minutes=1))
    paths = {item["source_path"] for item in candidates}

    assert "Inbox/process/cache/released-cache" in paths
    assert "Inbox/process/tmp/active-job" not in paths
    released_row = next(item for item in candidates if item["source_path"].endswith("released-cache"))
    assert released_row["category"] == "process_workspace"
    assert released_row["reason"] == "registered_process_artifact_released"


def test_clearup_inventory_integrates_only_registered_released_process_artifacts(tmp_path):
    from process_workspace import register_process_artifact, release_process_artifact
    from project_clearup import _collect_candidates

    root = _root(tmp_path)
    registered = root / "Inbox/process/tmp/registered"
    unregistered = root / "Inbox/process/tmp/unregistered"
    registered.mkdir(parents=True)
    unregistered.mkdir(parents=True)
    (registered / "x").write_text("x", encoding="utf-8")
    (unregistered / "y").write_text("y", encoding="utf-8")

    register_process_artifact(root, registered, owner="pytest", purpose="registered", kind="tmp")
    release_process_artifact(root, registered)

    candidates = _collect_candidates(root, keep_rollbacks=3)
    paths = {item["source_path"] for item in candidates}

    assert "Inbox/process/tmp/registered" in paths
    assert "Inbox/process/tmp/unregistered" not in paths
    assert "Inbox/process" not in paths
    assert "Inbox/process/process_map.json" not in paths


def test_hygiene_reports_unregistered_process_debris_and_released_registered_debt(tmp_path):
    from process_workspace import register_process_artifact, release_process_artifact
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    active = root / "Inbox/process/tmp/active"
    released = root / "Inbox/process/cache/released"
    unknown = root / "Inbox/process/tmp/unknown"
    for path in (active, released, unknown):
        path.mkdir(parents=True)
        (path / "payload.txt").write_text(path.name, encoding="utf-8")

    register_process_artifact(root, active, owner="pytest", purpose="active", kind="tmp")
    register_process_artifact(root, released, owner="pytest", purpose="released", kind="cache")
    release_process_artifact(root, released)

    check = project_hygiene_check(root)
    details = check["details"]

    assert check["status"] == "ORANGE"
    assert details["process_workspace_unregistered_count"] == 1
    assert details["process_workspace_released_count"] == 1
    assert details["process_workspace_active_count"] == 1
    assert details["process_workspace_unregistered"] == ["Inbox/process/tmp/unknown"]


def test_mode_entrypoint_initializes_process_workspace_before_background_workers():
    source = (ROOT / "tests/fixtures/pre57/mode_entrypoint.py").read_text(encoding="utf-8")
    assert "from process_workspace import ensure_process_workspace" in source
    start = source.index("def start_operating_mode_runtime()")
    end = source.index("\ndef main()", start)
    startup = source[start:end]
    bootstrap = startup.index("ReleaseTransitionCoordinator(root).bootstrap_legacy_if_needed()")
    process_init = startup.index("ensure_process_workspace(root)")
    workers = startup.index("_supervise_background_workers(root)")
    assert bootstrap < process_init < workers
