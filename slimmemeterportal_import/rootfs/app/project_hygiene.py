from __future__ import annotations

"""Lightweight, read-only project hygiene and ngrok safety checks.

These checks deliberately do not hash or move large trees.  They make stale
structure and insecure exposure visible to Projectmanager health while the
heavier project_clearup module remains responsible for dependency-audited moves.
"""

import json
import re
from pathlib import Path
from typing import Any


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[:4]) or (0,)


def _count_children(path: Path) -> int:
    try:
        return sum(1 for _ in path.iterdir()) if path.is_dir() else 0
    except OSError:
        return 0


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

    failed_release_count = sum(1 for path in root.glob("App.__failed_*") if path.exists())
    failed_inbox = root / "Inbox/failed"
    if failed_inbox.is_dir():
        try:
            failed_release_count += sum(
                1 for path in failed_inbox.iterdir() if path.exists() or path.is_symlink()
            )
        except OSError:
            pass
    restore_count = _count_children(root / "Backups/RestoreStaging")
    release_prepare_count = _count_children(root / "Backups/_release_prepare")
    release_builder_count = _count_children(root / "Data/03_Systeem/ReleaseBuilders")
    clearup_run_count = _count_children(root / "CLEARUP")

    known_staging_paths = (
        root / "_fix_backup_auto",
        root / "Data/03_Systeem/Debug",
        root / "Data/03_Systeem/Manuals/.@__thumb",
        root / "Data/03_Systeem/Projectmanager/_acceptance_retest_20260816",
        root / "Data/03_Systeem/Projectmanager/_mcp_write_test_20260816",
        root / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2",
        root / "Data/02_Output/Rapportages/share",
        root / "Data/02_Output/Rapportages/Data",
        root / "Inbox/release_hold_tmp",
        root / "Infra/Docker/native-mcp/_fix_backup",
        root / "Infra/Docker/native-mcp/_fix_backup_auto",
        root / "Infra/Docker/native-mcp/_permission_fix_backup",
    )
    known_staging_count = sum(1 for path in known_staging_paths if path.exists() or path.is_symlink())

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
        "mutated": False,
    }
    debt = (
        len(excess_rollbacks)
        + failed_release_count
        + restore_count
        + release_prepare_count
        + release_builder_count
        + known_staging_count
        + clearup_run_count
    )
    return {
        "name": "project_structure_hygiene",
        "status": "ORANGE" if debt else "GREEN",
        "reason": "cleanup_or_quarantine_pending" if debt else "clean",
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
