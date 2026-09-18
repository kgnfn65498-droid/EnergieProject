from __future__ import annotations

"""Fail-closed top-level structure policy for EnergieProject.

Only narrowly recognized release/development debris is eligible for CLEARUP.
Everything else outside canonical top-level namespaces is reported as
unclassified debt and left untouched until explicitly classified.
"""

import re
from pathlib import Path
from typing import Any

CANONICAL_ROOT_NAMES = frozenset({"App", "Backups", "Inbox", "Data", "Infra", "CLEARUP"})

_RELEASE_ZIP_RE = re.compile(r"^EnergieProject_v\d+(?:\.\d+)+(?:[^/]*)\.zip$", re.IGNORECASE)
_DEV_DEBT_RE = re.compile(
    r"^(?:tmp|temp|candidate|build|staging|repair)(?:[._-]|$)",
    re.IGNORECASE,
)
_WORKTREE_RE = re.compile(r"^v\d[0-9A-Za-z._-]*_work$", re.IGNORECASE)


def classify_root_entry(path: Path) -> str:
    name = Path(path).name
    if name in CANONICAL_ROOT_NAMES:
        return "canonical"
    if name.startswith("App.__rollback_"):
        return "managed_rollback"
    if name.startswith("App.__failed_"):
        return "managed_failed_release"
    if _RELEASE_ZIP_RE.fullmatch(name):
        return "release_zip"
    if name in {".DS_Store", "__pycache__", "_fix_backup_auto"}:
        return "development_debt"
    if _DEV_DEBT_RE.search(name) or _WORKTREE_RE.fullmatch(name):
        return "development_debt"
    return "unclassified"


def root_clearup_candidates(project_root: Path) -> list[dict[str, Any]]:
    root = Path(project_root)
    if not root.is_dir():
        return []
    result: list[dict[str, Any]] = []
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    for child in children:
        classification = classify_root_entry(child)
        if classification == "release_zip":
            result.append({
                "source_path": child.name,
                "reason": "root_release_zip_leftover",
                "category": "root_release_debt",
            })
        elif classification == "development_debt":
            result.append({
                "source_path": child.name,
                "reason": "root_development_artifact",
                "category": "root_development_debt",
            })
    return result


def root_structure_snapshot(project_root: Path) -> dict[str, Any]:
    root = Path(project_root)
    known: list[str] = []
    unknown: list[str] = []
    if not root.is_dir():
        return {
            "known_debt_count": 0,
            "known_debt": [],
            "unclassified_item_count": 0,
            "unclassified_items": [],
        }
    try:
        children = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return {
            "known_debt_count": 0,
            "known_debt": [],
            "unclassified_item_count": 1,
            "unclassified_items": ["<root-unreadable>"],
        }
    for child in children:
        classification = classify_root_entry(child)
        if classification in {"release_zip", "development_debt"}:
            known.append(child.name)
        elif classification == "unclassified":
            unknown.append(child.name)
    return {
        "known_debt_count": len(known),
        "known_debt": known,
        "unclassified_item_count": len(unknown),
        "unclassified_items": unknown,
    }
