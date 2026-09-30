from __future__ import annotations

import ast
import importlib.util
import json
import sys
import time
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
for value in (str(TOOLS), str(APP)):
    if value not in sys.path:
        sys.path.insert(0, value)

from ha_delivery_adapter import HADelivery
from release_controller import ReleaseController


def _module_value(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in statement.targets
        ):
            if not isinstance(statement.value, ast.Constant):
                raise AssertionError(f"{name} is not a constant in {path}")
            return str(statement.value.value)
    raise AssertionError(f"{name} missing from {path}")


def test_32530_release_identity_is_exact_across_all_runtime_sources():
    target = "32.5.30"
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == target
    assert yaml.safe_load((ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8"))["version"] == target
    assert _module_value(APP / "main.py", "APP_VERSION") == target
    assert _module_value(APP / "mode_entrypoint.py", "TARGET_RELEASE_VERSION") == target
    contract: dict = {}
    exec((ROOT / "release_test_contract.py").read_text(encoding="utf-8"), contract)
    assert contract["CURRENT_RELEASE"] == target


def test_32530_github_publisher_binding_imports_system_path_contract():
    module_path = ROOT / "tools/github_publisher_binding.py"
    source = module_path.read_text(encoding="utf-8")
    assert "from system_path_contract import project_system_path" in source
    spec = importlib.util.spec_from_file_location("publisher_binding_32530", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.project_system_path)


def test_32530_remote_predecessor_exact_pre_target_wait_is_bounded(tmp_path, monkeypatch):
    root = tmp_path
    (root / "App").mkdir()
    (root / "App/VERSIE.txt").write_text("32.5.29\n", encoding="utf-8")
    (root / "App/MANIFEST.sha256").write_text("base", encoding="utf-8")
    (root / "Inbox/processing").mkdir(parents=True)
    artifact = root / "Inbox/processing/EnergieProject_v32.5.30.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("MANIFEST.sha256", "target")
    import hashlib
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    state = ReleaseController().new_state(
        from_version="32.5.29",
        to_version="32.5.30",
        artifact_sha256=sha,
        artifact_name=artifact.name,
    )
    state.phase_started_at_epoch = time.time() - 3600

    delivery = HADelivery(root, timeout_seconds=1)
    payload = {
        "schema": "energie_ha_publication_contract_v2",
        "status": "publication_required",
        "source_stage": "processing_pre_target",
        "version": "32.5.30",
        "repository": "https://github.com/kgnfn65498-droid/EnergieProject",
        "branch": "main",
        "install_predecessor_version": "32.5.29",
        "install_predecessor_manifest_sha256": "install-manifest",
        "publication_predecessor_version": "32.5.28",
        "publication_predecessor_manifest_sha256": "pub-manifest",
        "expected_previous_version": "32.5.28",
        "expected_previous_manifest_sha256": "pub-manifest",
        "predecessor_version": "32.5.28",
        "predecessor_manifest_sha256": "pub-manifest",
        "target_manifest_sha256": delivery._target_manifest_sha(artifact),
        "processed_zip": artifact.name,
        "processed_zip_sha256": sha,
        "release_id": state.release_id,
        "generation": state.generation,
    }
    publication = {
        **payload,
        "published": True,
        "target_exact": True,
        "version": "32.5.28",
        "target_manifest_sha256": "pub-manifest",
        "remote_head": "abc",
        "local_head": "abc",
    }
    (root / "Inbox").mkdir(exist_ok=True)
    (root / "Inbox/github_publication_state.json").write_text(json.dumps(publication), encoding="utf-8")
    (root / "Inbox/ha_runtime").mkdir(parents=True)
    (root / "Inbox/ha_runtime/current.json").write_text(json.dumps({"version": "32.5.28"}), encoding="utf-8")

    monkeypatch.setattr(delivery, "_pre_target_contract", lambda _s, _artifact: payload)
    monkeypatch.setattr(delivery, "_ensure_contract", lambda _s, p, _marker: p)
    monkeypatch.setattr(delivery, "_reconcile_exact_publication", lambda _p: publication)
    monkeypatch.setattr(delivery, "_publisher_exact", lambda _pub, _payload: False)

    result = delivery.prepare_pre_target(state)
    assert result.status == "BLOCKED"
    assert result.reason == "github_pre_target_target_timeout"


def test_32530_manual_ha_wait_remains_unbounded_by_delivery_timeout(tmp_path):
    source = (ROOT / "tools/ha_delivery_adapter.py").read_text(encoding="utf-8")
    assert "WAITING_MANUAL_HA_UPDATE" in source
    align_start = source.index("    def align(")
    align = source[align_start:]
    waiting_pos = align.index("WAITING_MANUAL_HA_UPDATE")
    timeout_pos = align.index("elapsed=max")
    assert waiting_pos < timeout_pos


def test_32530_release_builder_refuses_split_runtime_identity(tmp_path):
    import shutil
    from release_artifact_builder import _verify_release_identity

    root = tmp_path / "release"
    (root / "slimmemeterportal_import/rootfs/app").mkdir(parents=True)
    shutil.copy2(ROOT / "VERSIE.txt", root / "VERSIE.txt")
    shutil.copy2(ROOT / "release_test_contract.py", root / "release_test_contract.py")
    shutil.copy2(ROOT / "slimmemeterportal_import/config.yaml", root / "slimmemeterportal_import/config.yaml")
    shutil.copy2(APP / "main.py", root / "slimmemeterportal_import/rootfs/app/main.py")
    shutil.copy2(APP / "mode_entrypoint.py", root / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py")

    assert _verify_release_identity(root) == "32.5.30"

    main_path = root / "slimmemeterportal_import/rootfs/app/main.py"
    main_path.write_text(
        main_path.read_text(encoding="utf-8").replace('APP_VERSION = "32.5.30"', 'APP_VERSION = "32.5.29"', 1),
        encoding="utf-8",
    )
    import pytest
    with pytest.raises(ValueError, match="release identity mismatch"):
        _verify_release_identity(root)


def test_32530_release_builder_refuses_missing_publisher_system_path_import(tmp_path):
    import shutil
    import pytest
    from release_artifact_builder import _verify_release_chain_contract

    root = tmp_path / "release"
    (root / "tools").mkdir(parents=True)
    source = ROOT / "tools/github_publisher_binding.py"
    target = root / "tools/github_publisher_binding.py"
    shutil.copy2(source, target)

    _verify_release_chain_contract(root)

    text = target.read_text(encoding="utf-8")
    text = text.replace("from system_path_contract import project_system_path\n", "")
    target.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="project_system_path import"):
        _verify_release_chain_contract(root)
