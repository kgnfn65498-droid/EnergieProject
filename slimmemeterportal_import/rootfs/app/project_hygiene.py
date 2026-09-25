from __future__ import annotations
from system_path_contract import project_system_path

"""Lightweight, read-only project hygiene and ngrok safety checks.

These checks deliberately do not hash or move large trees.  They make stale
structure and insecure exposure visible to Projectmanager health while the
heavier project_clearup module remains responsible for dependency-audited moves.
"""

import json
import re
from pathlib import Path

try:
    from process_workspace import inspect_process_workspace
except ModuleNotFoundError:  # standalone loader paths used by PM/watcher tools
    import importlib.util as _importlib_util
    _process_workspace_path = Path(__file__).resolve().parent / "process_workspace.py"
    _process_workspace_spec = _importlib_util.spec_from_file_location(
        "energie_process_workspace_impl", _process_workspace_path
    )
    if _process_workspace_spec is None or _process_workspace_spec.loader is None:
        raise ImportError(f"Cannot load process workspace implementation: {_process_workspace_path}")
    _process_workspace_module = _importlib_util.module_from_spec(_process_workspace_spec)
    _process_workspace_spec.loader.exec_module(_process_workspace_module)
    inspect_process_workspace = _process_workspace_module.inspect_process_workspace
from typing import Any

try:
    from root_structure_policy import root_structure_snapshot
except ModuleNotFoundError:
    import importlib.util as _root_importlib_util
    _root_policy_path = Path(__file__).resolve().parent / "root_structure_policy.py"
    _root_policy_spec = _root_importlib_util.spec_from_file_location(
        "energie_root_structure_policy_impl", _root_policy_path
    )
    if _root_policy_spec is None or _root_policy_spec.loader is None:
        raise ImportError(f"Cannot load root structure policy: {_root_policy_path}")
    _root_policy_module = _root_importlib_util.module_from_spec(_root_policy_spec)
    _root_policy_spec.loader.exec_module(_root_policy_module)
    root_structure_snapshot = _root_policy_module.root_structure_snapshot


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[:4]) or (0,)


def _count_children(path: Path) -> int:
    try:
        return sum(1 for _ in path.iterdir()) if path.is_dir() else 0
    except OSError:
        return 0






def _children_relative(root: Path, parent_rel: str) -> list[str]:
    parent = root / parent_rel
    try:
        if not parent.is_dir():
            return []
        return sorted((Path(parent_rel) / child.name).as_posix() for child in parent.iterdir())
    except OSError:
        return []


def _current_release(root: Path) -> str:
    try:
        return (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _current_clearup_review_paths(root: Path, *, release_version: str) -> tuple[set[str], bool, str]:
    runtime = _read_json(project_system_path(root, 'Inbox/logs/project_clearup_runtime.json')) or {}
    done = str(runtime.get("status") or "") in {"completed", "already_completed", "no_action"}
    if not done or str(runtime.get("release_version") or "") != str(release_version or ""):
        return set(), False, "runtime_not_current_completed"
    manifest_rel = str(runtime.get("manifest") or "").strip()
    plan_id = str(runtime.get("plan_id") or "").strip()
    if not manifest_rel or not plan_id:
        return set(), False, "runtime_manifest_or_plan_missing"
    manifest_path = (root / manifest_rel).resolve(strict=False)
    clearup_root = (root / "CLEARUP").resolve(strict=False)
    if manifest_path == clearup_root or clearup_root not in manifest_path.parents:
        return set(), False, "manifest_outside_clearup"
    manifest = _read_json(manifest_path) or {}
    if (
        str(manifest.get("current_version") or "") != str(release_version or "")
        or str(manifest.get("plan_id") or "") != plan_id
    ):
        return set(), False, "manifest_identity_mismatch"
    review_items = manifest.get("review_items")
    if not isinstance(review_items, list):
        return set(), False, "review_items_missing"
    paths: set[str] = set()
    for item in review_items:
        if not isinstance(item, dict) or str(item.get("disposition") or "REVIEW") != "REVIEW":
            continue
        relative = str(item.get("source_path") or "").strip().strip("/")
        if relative and not relative.startswith("../") and "/../" not in relative:
            paths.add(relative)
    return paths, True, "current_completed_review_manifest"


def _inbox_development_debt(root: Path) -> tuple[int, int, list[str]]:
    """Count development debris at Inbox root while allowing canonical Inbox/Develop.

    Operational runtime namespaces are not debt. Development artifacts must live
    under one canonical Inbox/Develop subtree so the Inbox root remains stable.
    """
    inbox = root / "Inbox"
    develop = inbox / "Develop"
    develop_children = _count_children(develop)
    if not inbox.is_dir():
        return develop_children, 0, []
    operational = {
        "Develop", "incoming", "processed", "processing", "failed", "logs",
        "projectmanager_v2", "operating_mode", "control_plane", "native_mcp_runtime",
        "nas_container_cr_local", "project_cr_local",
    }
    pattern = re.compile(r"^(?:attempt|dev|develop|test|tmp|temp|repair|staging|candidate|build)(?:[._-]|$)|(?:[._-](?:tmp|temp|test|dev))$", re.IGNORECASE)
    debt: list[str] = []
    try:
        for path in inbox.iterdir():
            if path.name in operational:
                continue
            if pattern.search(path.name):
                debt.append(path.name)
    except OSError:
        return develop_children, 0, []
    return develop_children, len(debt), sorted(debt)

def project_hygiene_check(project_root: Path, *, keep_rollbacks: int = 3) -> dict[str, Any]:
    """Report structural cleanup debt without mutating or recursively hashing it."""
    root = Path(project_root)
    rollbacks: list[tuple[tuple[int, ...], str]] = []
    try:
        rollback_paths = list(root.glob("App.__rollback_*"))
    except OSError:
        rollback_paths = []
    for path in rollback_paths:
        if not path.is_dir():
            continue
        version_file = path / "VERSIE.txt"
        try:
            version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else path.name.rsplit("_", 1)[-1]
        except OSError:
            version = path.name.rsplit("_", 1)[-1]
        rollbacks.append((_version_tuple(version), path.name))
    rollbacks.sort(reverse=True)
    excess_rollbacks = [name for _, name in rollbacks[max(0, int(keep_rollbacks)):]]

    failed_release_paths = sorted(
        path.relative_to(root).as_posix()
        for path in root.glob("App.__failed_*")
        if path.exists() or path.is_symlink()
    )
    failed_release_paths += _children_relative(root, "Inbox/failed")
    failed_release_count = len(failed_release_paths)
    restore_paths = _children_relative(root, "Backups/RestoreStaging")
    release_prepare_paths = _children_relative(root, "Backups/_release_prepare")
    release_builder_paths = _children_relative(root, "Data/03_Systeem/ReleaseBuilders")
    restore_count = len(restore_paths)
    release_prepare_count = len(release_prepare_paths)
    release_builder_count = len(release_builder_paths)
    clearup_run_count = _count_children(root / "CLEARUP")
    inbox_develop_count, inbox_root_debt_count, inbox_root_debt = _inbox_development_debt(root)
    process_workspace = inspect_process_workspace(root)
    root_structure = root_structure_snapshot(root)

    known_staging_paths = (
        root / "_fix_backup_auto",
        root / "Data/03_Systeem/Debug",
        root / "Data/03_Systeem/Manuals/.@__thumb",
        root / "Data/03_Systeem/Projectmanager/_acceptance_retest_20260816",
        root / "Data/03_Systeem/Projectmanager/_mcp_write_test_20260816",
        root / "Data/02_Output/Rapportages/share",
        root / "Data/02_Output/Rapportages/Data",
        root / "Inbox/release_hold_tmp",
        root / "Infra/Docker/native-mcp/_fix_backup",
        root / "Infra/Docker/native-mcp/_fix_backup_auto",
        root / "Infra/Docker/native-mcp/_permission_fix_backup",
    )
    known_staging_debt = sorted(
        path.relative_to(root).as_posix()
        for path in known_staging_paths
        if path.exists() or path.is_symlink()
    )
    # ProjectManagerV2 staging is managed per child by CLEARUP. The stable
    # parent directory may intentionally remain present and is not debt by
    # itself; only residual children count.
    known_staging_debt += _children_relative(
        root, "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2"
    )
    known_staging_debt = sorted(set(known_staging_debt))
    known_staging_count = len(known_staging_debt)

    legacy_debt_paths = set(excess_rollbacks)
    legacy_debt_paths.update(failed_release_paths)
    legacy_debt_paths.update(restore_paths)
    legacy_debt_paths.update(release_prepare_paths)
    legacy_debt_paths.update(release_builder_paths)
    legacy_debt_paths.update(known_staging_debt)
    legacy_debt_paths.update(f"Inbox/{name}" for name in inbox_root_debt)

    release_version = _current_release(root)
    reviewed_paths, review_evidence_current, review_evidence_reason = _current_clearup_review_paths(
        root, release_version=release_version
    )
    reviewed_hygiene_debt = sorted(legacy_debt_paths & reviewed_paths) if review_evidence_current else []
    unreviewed_hygiene_debt = sorted(legacy_debt_paths - set(reviewed_hygiene_debt))

    details = {
        "rollback_total_count": len(rollbacks),
        "rollback_keep_count": min(len(rollbacks), max(0, int(keep_rollbacks))),
        "rollback_excess_count": len(excess_rollbacks),
        "rollback_excess": excess_rollbacks,
        "failed_release_count": failed_release_count,
        "restore_staging_child_count": restore_count,
        "release_prepare_child_count": release_prepare_count,
        "release_builder_child_count": release_builder_count,
        "known_staging_path_count": known_staging_count,
        "clearup_run_count": clearup_run_count,
        "inbox_develop_child_count": inbox_develop_count,
        "inbox_root_development_debt_count": inbox_root_debt_count,
        "inbox_root_development_debt": inbox_root_debt,
        "process_workspace_active_count": int(process_workspace.get("active_count") or 0),
        "process_workspace_released_count": int(process_workspace.get("released_count") or 0),
        "process_workspace_unregistered_count": int(process_workspace.get("unregistered_count") or 0),
        "process_workspace_unregistered": list(process_workspace.get("unregistered") or []),
        "process_workspace_invalid_entry_count": int(process_workspace.get("invalid_entry_count") or 0),
        "root_known_debt_count": int(root_structure.get("known_debt_count") or 0),
        "root_known_debt": list(root_structure.get("known_debt") or []),
        "root_unclassified_item_count": int(root_structure.get("unclassified_item_count") or 0),
        "root_unclassified_items": list(root_structure.get("unclassified_items") or []),
        "clearup_review_evidence_current": review_evidence_current,
        "clearup_review_evidence_reason": review_evidence_reason,
        "reviewed_hygiene_debt_count": len(reviewed_hygiene_debt),
        "reviewed_hygiene_debt": reviewed_hygiene_debt,
        "unreviewed_hygiene_debt_count": len(unreviewed_hygiene_debt),
        "unreviewed_hygiene_debt": unreviewed_hygiene_debt,
        "mutated": False,
    }
    debt = (
        len(unreviewed_hygiene_debt)
        + int(process_workspace.get("released_count") or 0)
        + int(process_workspace.get("unregistered_count") or 0)
        + int(process_workspace.get("invalid_entry_count") or 0)
        + int(root_structure.get("known_debt_count") or 0)
        + int(root_structure.get("unclassified_item_count") or 0)
        # CLEARUP is intentional reversible quarantine. Existing runs are
        # evidence/history, not live-structure debt.
    )
    return {
        "name": "project_structure_hygiene",
        "status": "ORANGE" if debt else "GREEN",
        "reason": (
            "cleanup_or_quarantine_pending"
            if debt
            else ("clean_reviewed_debt_preserved" if reviewed_hygiene_debt else "clean")
        ),
        "evidence_ref": str(root),
        "evidence_strength": "verified",
        "details": details,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def ngrok_security_check(project_root: Path) -> dict[str, Any]:
    """Fail visibly unless the external ngrok boundary is independently proven.

    A compose target alone can never prove OAuth/OIDC, route restriction,
    header stripping and rate limiting because those controls may live at the
    ngrok edge.  A full native MCP tunnel is explicitly considered unsecured.
    """
    root = Path(project_root)
    compose = root / "Infra/docker-compose.yml"
    try:
        text = compose.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "name": "ngrok_security",
            "status": "ORANGE",
            "reason": "ngrok_configuration_unreadable",
            "evidence_ref": str(compose),
            "evidence_strength": "unverified",
            "details": {"error": str(exc)},
        }

    # Keep this intentionally conservative and dependency-light.  We only need
    # to identify the dangerous full-MCP target and whether an independently
    # verified acceptance record exists for the intended external PM boundary.
    has_ngrok = bool(re.search(r"(?m)^\s{0,4}ngrok:\s*$", text))
    targets = re.findall(r"(?:127\.0\.0\.1|localhost):\d+", text)
    target = targets[-1] if targets else None
    if not has_ngrok:
        return {
            "name": "ngrok_security",
            "status": "ORANGE",
            "reason": "ngrok_not_configured",
            "evidence_ref": str(compose),
            "evidence_strength": "verified",
            "details": {"target": target},
        }
    if target and target.endswith(":8000"):
        return {
            "name": "ngrok_security",
            "status": "ORANGE",
            "reason": "full_native_mcp_tunnel_not_secured",
            "evidence_ref": str(compose),
            "evidence_strength": "verified",
            "details": {"target": target, "full_native_mcp": True, "edge_security_verified": False},
        }

    acceptance_path = root / "Data/03_Systeem/Projectmanager/State/ngrok_security_acceptance.json"
    acceptance = _read_json(acceptance_path)
    verified = bool(
        acceptance
        and acceptance.get("status") == "verified"
        and acceptance.get("edge_auth_verified") is True
        and acceptance.get("route_restriction_verified") is True
        and acceptance.get("rate_limit_verified") is True
        and acceptance.get("header_policy_verified") is True
        and acceptance.get("target_route") == "/api/projectmanager/external/conversation"
        and acceptance.get("full_8099_exposure") is False
    )
    if verified:
        return {
            "name": "ngrok_security",
            "status": "GREEN",
            "reason": "dedicated_external_pm_boundary_verified",
            "evidence_ref": str(acceptance_path),
            "evidence_strength": "verified",
            "details": {"target": target, "edge_security_verified": True},
        }
    return {
        "name": "ngrok_security",
        "status": "ORANGE",
        "reason": "edge_security_not_proven",
        "evidence_ref": str(compose),
        "evidence_strength": "verified",
        "details": {"target": target, "edge_security_verified": False},
    }
