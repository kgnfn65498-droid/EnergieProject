from __future__ import annotations

"""Reversible project housekeeping for EnergieProject 32.4.25+.

The module deliberately implements no delete operation.  Proven-obsolete items
are hard-renamed into a CLEARUP quarantine on the same filesystem.  The old
path therefore disappears completely: no symlink, alias, bind mount or fallback
is created.  Every move is dependency-audited immediately before execution and
is recorded in a restorable manifest.
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA = "energie_project_clearup_v1"
TEXT_SUFFIXES = {
    "", ".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".ini", ".conf",
    ".cfg", ".py", ".sh", ".command", ".env", ".toml", ".service",
}
MAX_SCAN_BYTES = 2_000_000


class ClearupExecutionTimeout(RuntimeError):
    def __init__(self, phase: str, *, candidate: str | None = None):
        self.phase = str(phase or "unknown")
        self.candidate = candidate
        detail = f"CLEARUP execution timeout in phase={self.phase}"
        if candidate:
            detail += f" candidate={candidate}"
        super().__init__(detail)


def _check_deadline(deadline_monotonic: float | None, phase: str, *, candidate: str | None = None) -> None:
    if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
        raise ClearupExecutionTimeout(phase, candidate=candidate)


def _emit_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    phase: str,
    started_monotonic: float | None,
    **details: Any,
) -> None:
    if progress_callback is None:
        return
    started = time.monotonic() if started_monotonic is None else float(started_monotonic)
    payload = {
        "phase": str(phase),
        "elapsed_seconds": round(max(0.0, time.monotonic() - started), 3),
        **details,
    }
    progress_callback(payload)

ACTIVE_SCAN_ROOTS = (
    "App/slimmemeterportal_import/rootfs/app",
    "App/slimmemeterportal_import/config.yaml",
    "Infra",
    "Inbox",
    "Data/03_Systeem/Projectmanager/Roadmap",
    "Data/03_Systeem/Projectmanager/Policies",
    "Data/03_Systeem/Projectmanager/State",
)

# These are never candidates in this module.  Some parents contain allowlisted
# stale children (for example RestoreStaging); only the child is quarantined.
PROTECTED_PREFIXES = (
    "App/",
    "Backups/CrashRecovery",
    "Backups/NAS Container",
    "Backups/Status",
    "Data/01_Input/",
    "Data/02_Output/Rapportages/KnowledgeBase",
    "Data/02_Output/Rapportages/Verbruikshistorie",
    "Inbox/incoming",
    "Inbox/processing",
    "Inbox/processed",
    "Inbox/operating_mode",
    "Inbox/projectmanager_v2",
)
PROTECTED_EXACT = {
    "App",
    "Infra",
    "Inbox",
    "Backups",
    "Data",
    "CLEARUP",
    "Inbox/atomic_app_swap_state.json",
    "Inbox/github_publication_state.json",
    "Inbox/watcher_heartbeat.v2",
    "Inbox/.watcher.heartbeat",
}


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[:4]) or (0,)


def _hash_file(
    path: Path,
    *,
    deadline_monotonic: float | None = None,
    phase: str = "candidate_hash",
    candidate: str | None = None,
) -> str:
    digest = hashlib.sha256()
    _check_deadline(deadline_monotonic, phase, candidate=candidate)
    with path.open("rb") as handle:
        while True:
            _check_deadline(deadline_monotonic, phase, candidate=candidate)
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(
    path: Path,
    *,
    deadline_monotonic: float | None = None,
    phase: str = "candidate_hash",
    candidate: str | None = None,
) -> str:
    """Stable hash for a file or directory tree, including empty directories."""
    path = Path(path)
    _check_deadline(deadline_monotonic, phase, candidate=candidate)
    digest = hashlib.sha256()
    if path.is_symlink():
        digest.update(b"SYMLINK\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return digest.hexdigest()
    if path.is_file():
        digest.update(b"FILE\0")
        digest.update(_hash_file(path, deadline_monotonic=deadline_monotonic, phase=phase, candidate=candidate).encode("ascii"))
        return digest.hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest.update(b"DIR\0")
    for item in sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix()):
        _check_deadline(deadline_monotonic, phase, candidate=candidate)
        rel = item.relative_to(path).as_posix().encode("utf-8", errors="surrogateescape")
        if item.is_symlink():
            digest.update(b"L\0" + rel + b"\0")
            digest.update(os.readlink(item).encode("utf-8", errors="surrogateescape"))
        elif item.is_dir():
            digest.update(b"D\0" + rel + b"\0")
        elif item.is_file():
            digest.update(b"F\0" + rel + b"\0")
            digest.update(_hash_file(item, deadline_monotonic=deadline_monotonic, phase=phase, candidate=candidate).encode("ascii"))
    return digest.hexdigest()


def _tree_sha256_runtime(
    path: Path, *, deadline_monotonic: float | None, phase: str, candidate: str | None
) -> str:
    # Preserve the historical one-argument tree_sha256 call contract when no
    # deadline is active; existing test/instrumentation wrappers rely on it.
    if deadline_monotonic is None:
        return tree_sha256(path)
    return tree_sha256(
        path, deadline_monotonic=deadline_monotonic, phase=phase, candidate=candidate
    )


def _size_bytes(path: Path, *, deadline_monotonic: float | None = None, candidate: str | None = None) -> int:
    _check_deadline(deadline_monotonic, "candidate_inventory", candidate=candidate)
    if path.is_file() or path.is_symlink():
        try:
            return int(path.lstat().st_size)
        except OSError:
            return 0
    total = 0
    for item in path.rglob("*"):
        _check_deadline(deadline_monotonic, "candidate_inventory", candidate=candidate)
        if item.is_file() and not item.is_symlink():
            try:
                total += int(item.stat().st_size)
            except OSError:
                pass
    return total


def _is_protected(relative: str) -> bool:
    rel = relative.rstrip("/")
    if rel in PROTECTED_EXACT:
        return True
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _add_candidate(store: dict[str, dict[str, Any]], root: Path, path: Path, *, reason: str, category: str) -> None:
    try:
        relative = _rel(path, root)
    except ValueError:
        return
    if relative.startswith("CLEARUP/") or relative == "CLEARUP" or _is_protected(relative):
        return
    if not path.exists() and not path.is_symlink():
        return
    store.setdefault(relative, {
        "source_path": relative,
        "reason": reason,
        "category": category,
    })


def _collect_candidates(root: Path, *, keep_rollbacks: int) -> list[dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}

    rollbacks: list[tuple[tuple[int, ...], Path]] = []
    for path in root.glob("App.__rollback_*"):
        if not path.is_dir():
            continue
        version_file = path / "VERSIE.txt"
        version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else path.name.split("App.__rollback_", 1)[-1]
        rollbacks.append((_version_tuple(version), path))
    rollbacks.sort(key=lambda item: item[0], reverse=True)
    for _, path in rollbacks[max(0, int(keep_rollbacks)):]:
        _add_candidate(items, root, path, reason="rollback_outside_retention", category="release_rollback")

    for path in root.glob("App.__failed_*"):
        _add_candidate(items, root, path, reason="failed_release_artifact", category="failed_release")
    _add_candidate(items, root, root / "_fix_backup_auto", reason="obsolete_fix_staging", category="repair_staging")

    exact_dirs = (
        "Data/03_Systeem/Debug",
        "Data/03_Systeem/Manuals/.@__thumb",
        "Data/03_Systeem/Projectmanager/_acceptance_retest_20260816",
        "Data/03_Systeem/Projectmanager/_mcp_write_test_20260816",
        "Data/02_Output/Rapportages/share",
        "Data/02_Output/Rapportages/Data",
        "Inbox/release_hold_tmp",
        "Infra/Docker/native-mcp/_fix_backup",
        "Infra/Docker/native-mcp/_fix_backup_auto",
        "Infra/Docker/native-mcp/_permission_fix_backup",
    )
    for relative in exact_dirs:
        _add_candidate(items, root, root / relative, reason="audited_obsolete_staging", category="staging")

    # PM build staging is intentionally classified per direct child. RuntimeV2
    # can retain historical references to one repair artifact; that must block
    # only the referenced child, not every unrelated old build tree.
    pm_staging = root / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2"
    if pm_staging.is_dir():
        for child in sorted(pm_staging.iterdir(), key=lambda p: p.name):
            _add_candidate(
                items, root, child,
                reason="obsolete_projectmanager_build_staging",
                category="projectmanager_staging",
            )

    for hidden in (root / "Data/02_Output/Rapportages").glob(".KnowledgeBase*_rehome*") if (root / "Data/02_Output/Rapportages").is_dir() else []:
        _add_candidate(items, root, hidden, reason="completed_structure_migration_staging", category="migration_staging")

    for parent_rel, reason, category in (
        ("Backups/RestoreStaging", "completed_restore_drill_extract", "restore_staging"),
        ("Backups/_release_prepare", "obsolete_release_prepare_tree", "release_staging"),
        ("Data/03_Systeem/ReleaseBuilders", "obsolete_release_builder", "release_builder"),
    ):
        parent = root / parent_rel
        if parent.is_dir():
            for child in sorted(parent.iterdir(), key=lambda p: p.name):
                _add_candidate(items, root, child, reason=reason, category=category)

    failed = root / "Inbox/failed"
    if failed.is_dir():
        for child in sorted(failed.iterdir(), key=lambda p: p.name):
            _add_candidate(items, root, child, reason="settled_failed_release", category="failed_release")

    # 32.4.41: ad-hoc development debris may no longer accumulate directly
    # under Inbox.  Long-lived development material belongs below Inbox/Develop;
    # only narrowly identified loose dev/temp names are quarantine candidates.
    inbox = root / "Inbox"
    if inbox.is_dir():
        for child in sorted(inbox.iterdir(), key=lambda p: p.name):
            name = child.name.lower()
            if name == "develop":
                continue
            if name.startswith(("attempt_", "dev_", "tmp_", "temp_", "staging_")):
                _add_candidate(
                    items, root, child,
                    reason="loose_inbox_development_debt",
                    category="inbox_development_debt",
                )

    infra = root / "Infra"
    if infra.is_dir():
        for child in infra.glob("*.pre_*"):
            _add_candidate(items, root, child, reason="obsolete_pre_fix_copy", category="infra_backup")

    # macOS resource-fork residue has no executable value and is safe only after
    # the normal dependency scan below finds no live reference.
    epex_manual = root / "Data/01_Input/EPEX manual downlaod"
    if epex_manual.is_dir():
        for child in epex_manual.glob("._*"):
            # This is a narrow exception inside Data/01_Input: only AppleDouble
            # metadata is ever considered, never actual month/source data.
            relative = _rel(child, root)
            items.setdefault(relative, {
                "source_path": relative,
                "reason": "macos_appledouble_metadata",
                "category": "filesystem_metadata",
            })

    return [items[key] for key in sorted(items)]


def _candidate_ancestor(relative: str, candidate_paths: set[str]) -> bool:
    return any(relative == cand or relative.startswith(cand.rstrip("/") + "/") for cand in candidate_paths)


def _iter_active_text_files(root: Path, candidate_paths: set[str], *, deadline_monotonic: float | None = None) -> Iterable[Path]:
    seen: set[str] = set()
    for root_rel in ACTIVE_SCAN_ROOTS:
        _check_deadline(deadline_monotonic, "dependency_index")
        active_root = root / root_rel
        if not active_root.exists():
            continue
        paths = [active_root] if active_root.is_file() else active_root.rglob("*")
        for path in paths:
            _check_deadline(deadline_monotonic, "dependency_index")
            if not path.is_file() or path.is_symlink():
                continue
            relative = _rel(path, root)
            if relative.startswith("CLEARUP/") or _candidate_ancestor(relative, candidate_paths):
                continue
            if relative in seen:
                continue
            seen.add(relative)
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > MAX_SCAN_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _reference_is_informational(relative: str) -> bool:
    """References that observe housekeeping are evidence, not consumers.

    Executable/runtime configuration references still block.  Markdown and the
    housekeeping modules are descriptive.  Projectmanager status/snapshot JSON
    under RuntimeV2 is also derived observation output: it reports stale paths
    (for example rollback_excess) but never consumes those paths.  Treating
    those files as hard dependencies creates a self-blocking feedback loop and
    can make the second fail-closed audit differ from the first while PM updates
    its status during the same CLEARUP run.
    """
    path = Path(relative)
    if path.suffix.lower() == ".md":
        return True
    if path.name in {"project_clearup.py", "project_hygiene.py"}:
        return True
    rel = relative.replace("\\", "/")
    return (
        rel.startswith("Inbox/projectmanager_v2/RuntimeV2/status/")
        or rel.startswith("Inbox/projectmanager_v2/RuntimeV2/snapshots/")
        or rel == "Data/03_Systeem/Projectmanager/State/project_clearup_runtime.json"
        or rel == "Inbox/logs/project_clearup_runtime.json"
        or rel == "Inbox/project_clearup_move_request.json"
        or rel == "Inbox/logs/project_clearup_move_result.json"
    )


def _build_active_dependency_index(
    root: Path, candidate_paths: set[str], active_files: list[Path], *, deadline_monotonic: float | None = None
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Inventory active text and symlink dependencies exactly once per plan.

    32.4.25 re-read every active text file and re-walked every active symlink
    surface once *per cleanup candidate*.  On the real EnergieProject tree that
    made a safe audit practically unbounded.  This index preserves the same
    fail-closed matching semantics while moving all filesystem I/O to one pass.
    """
    candidates = sorted(candidate_paths)
    blocking: dict[str, list[dict[str, Any]]] = {candidate: [] for candidate in candidates}
    informational: dict[str, list[dict[str, Any]]] = {candidate: [] for candidate in candidates}

    # Read each eligible active text file once, then match all candidate needles
    # against the in-memory text.  Basename matching is intentionally preserved
    # because 32.4.25 treated both full relative paths and basenames as evidence.
    for path in active_files:
        _check_deadline(deadline_monotonic, "dependency_index")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = _rel(path, root)
        is_informational = _reference_is_informational(relative)
        for candidate in candidates:
            needles = {candidate, Path(candidate).name}
            matched = sorted(needle for needle in needles if needle and needle in text)
            if not matched:
                continue
            ref = {"path": relative, "matches": matched}
            target = informational[candidate] if is_informational else blocking[candidate]
            target.append(ref)

    # Walk each active surface once for symlinks.  A symlink is always a hard
    # dependency, exactly as in 32.4.25.  Deduplication protects overlapping
    # active roots without weakening matching.
    resolved_targets = {candidate: (root / candidate).resolve(strict=False) for candidate in candidates}
    seen_symlinks: set[str] = set()
    for active_root_rel in ACTIVE_SCAN_ROOTS:
        _check_deadline(deadline_monotonic, "dependency_index")
        active_root = root / active_root_rel
        if not active_root.exists() or active_root.is_file():
            continue
        try:
            iterator = active_root.rglob("*")
        except OSError:
            continue
        for path in iterator:
            _check_deadline(deadline_monotonic, "dependency_index")
            if not path.is_symlink():
                continue
            relative = _rel(path, root)
            if relative in seen_symlinks:
                continue
            seen_symlinks.add(relative)
            if relative.startswith("CLEARUP/") or _candidate_ancestor(relative, candidate_paths):
                continue
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                continue
            for candidate, target in resolved_targets.items():
                if resolved == target or target in resolved.parents:
                    blocking[candidate].append({"path": relative, "matches": ["symlink_dependency"]})

    return blocking, informational


def _active_references(
    candidate_rel: str,
    dependency_index: tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return copied dependency evidence for one candidate from the shared index."""
    blocking, informational = dependency_index
    return list(blocking.get(candidate_rel, [])), list(informational.get(candidate_rel, []))

def _atomic_rollback_reference(root: Path) -> str | None:
    path = root / "Inbox/atomic_app_swap_state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = str(data.get("rollback_path") or "").strip()
    if value.startswith("/"):
        try:
            value = Path(value).resolve(strict=False).relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            return None
    return value or None


def build_clearup_plan(
    project_root: Path,
    *,
    current_version: str,
    keep_rollbacks: int = 3,
    deadline_monotonic: float | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    started_monotonic: float | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    _check_deadline(deadline_monotonic, "candidate_inventory")
    raw_items = _collect_candidates(root, keep_rollbacks=keep_rollbacks)
    _emit_progress(
        progress_callback, phase="candidate_inventory", started_monotonic=started_monotonic,
        candidate_total=len(raw_items),
    )
    candidate_paths = {item["source_path"] for item in raw_items}
    active_files = list(_iter_active_text_files(root, candidate_paths, deadline_monotonic=deadline_monotonic))
    dependency_index = _build_active_dependency_index(
        root, candidate_paths, active_files, deadline_monotonic=deadline_monotonic
    )
    _emit_progress(
        progress_callback, phase="dependency_index", started_monotonic=started_monotonic,
        candidate_total=len(raw_items), active_file_count=len(active_files),
    )
    atomic_rollback = _atomic_rollback_reference(root)

    items: list[dict[str, Any]] = []
    total = len(raw_items)
    for index, base in enumerate(raw_items, 1):
        relative = base["source_path"]
        _check_deadline(deadline_monotonic, "candidate_hash", candidate=relative)
        _emit_progress(
            progress_callback, phase="candidate_hash", started_monotonic=started_monotonic,
            candidate=relative, candidate_index=index, candidate_total=total, stage="plan",
        )
        source = root / relative
        refs, informational_refs = _active_references(relative, dependency_index)
        if atomic_rollback == relative:
            refs.append({"path": "Inbox/atomic_app_swap_state.json", "matches": ["current_atomic_rollback"]})
        disposition = "REVIEW" if refs else "CLEARUP"
        candidate_read_error = None
        size_bytes = None
        tree_hash = None
        try:
            size_bytes = _size_bytes(source, deadline_monotonic=deadline_monotonic, candidate=relative)
            tree_hash = _tree_sha256_runtime(
                source, deadline_monotonic=deadline_monotonic, phase="candidate_hash", candidate=relative
            )
        except OSError as exc:
            # Fail closed per candidate: unreadable or otherwise inaccessible
            # candidates cannot be content-verified and therefore may never be
            # moved.  Keep the rest of the plan usable so one historical tree
            # cannot abort housekeeping for unrelated proven-safe candidates.
            disposition = "REVIEW"
            candidate_read_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        items.append({
            **base,
            "type": "symlink" if source.is_symlink() else ("directory" if source.is_dir() else "file"),
            "size_bytes": size_bytes,
            "tree_sha256": tree_hash,
            "candidate_read_error": candidate_read_error,
            "active_references": refs,
            "informational_references": informational_refs,
            "disposition": disposition,
        })

    identity = {
        "schema": SCHEMA,
        "current_version": str(current_version),
        "keep_rollbacks": int(keep_rollbacks),
        "items": [{
            "source_path": item["source_path"],
            "tree_sha256": item["tree_sha256"],
            "candidate_read_error": item.get("candidate_read_error"),
            "disposition": item["disposition"],
            "active_references": item["active_references"],
            "informational_references": item.get("informational_references", []),
        } for item in items],
    }
    plan_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    return {
        **identity,
        "plan_id": plan_id,
        "confirmation_required": f"MOVE TO CLEARUP {plan_id}",
        "clearup_count": sum(1 for item in items if item["disposition"] == "CLEARUP"),
        "review_count": sum(1 for item in items if item["disposition"] == "REVIEW"),
        "items": items,
        "delete_capability": False,
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _safe_run_id(value: str) -> str:
    run_id = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", run_id):
        raise ValueError("ongeldige CLEARUP run_id")
    return run_id


def apply_clearup_plan(
    project_root: Path,
    plan: dict[str, Any],
    *,
    confirmation: str,
    run_id: str | None = None,
    deadline_monotonic: float | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    started_monotonic: float | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    _check_deadline(deadline_monotonic, "apply")
    if confirmation != plan.get("confirmation_required"):
        raise ValueError(f"Bevestiging ongeldig. Verwacht exact: {plan.get('confirmation_required')}")
    # Revalidate candidate membership and active dependencies immediately before
    # moving, but do not re-hash every candidate tree here.  The original plan
    # already carries a full content hash; each CLEARUP item is hashed once more
    # directly before its hard rename below.  This keeps the dependency audit
    # fresh/fail-closed without multiplying multi-GB NAS reads.
    raw_items = _collect_candidates(root, keep_rollbacks=int(plan.get("keep_rollbacks") or 3))
    _check_deadline(deadline_monotonic, "dependency_index")
    candidate_paths = {item["source_path"] for item in raw_items}
    planned_paths = {str(item.get("source_path") or "") for item in (plan.get("items") or [])}
    if candidate_paths != planned_paths:
        raise RuntimeError("CLEARUP-plan is gewijzigd; nieuwe dependency-audit vereist.")
    active_files = list(_iter_active_text_files(root, candidate_paths, deadline_monotonic=deadline_monotonic))
    dependency_index = _build_active_dependency_index(
        root, candidate_paths, active_files, deadline_monotonic=deadline_monotonic
    )
    atomic_rollback = _atomic_rollback_reference(root)
    planned_by_path = {str(item["source_path"]): item for item in (plan.get("items") or [])}
    for base in raw_items:
        relative = base["source_path"]
        refs, informational_refs = _active_references(relative, dependency_index)
        if atomic_rollback == relative:
            refs.append({"path": "Inbox/atomic_app_swap_state.json", "matches": ["current_atomic_rollback"]})
        previous = planned_by_path[relative]
        disposition = "REVIEW" if refs or previous.get("candidate_read_error") else "CLEARUP"
        if (
            disposition != previous.get("disposition")
            or refs != list(previous.get("active_references") or [])
        ):
            raise RuntimeError(f"CLEARUP dependency-audit gewijzigd; nieuwe plancontrole vereist: {relative}")
        # Observation-only evidence may legitimately change while PM refreshes
        # status/snapshots.  Refresh it for the manifest, but never turn that
        # non-consuming telemetry churn into a hard dependency failure.
        previous["informational_references"] = informational_refs

    fresh = plan
    _check_deadline(deadline_monotonic, "apply")
    _emit_progress(
        progress_callback, phase="apply", started_monotonic=started_monotonic,
        candidate_total=sum(1 for item in fresh["items"] if item["disposition"] == "CLEARUP"),
    )
    run_id = _safe_run_id(run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    run_root = root / "CLEARUP" / run_id
    original_root = run_root / "original"
    if run_root.exists():
        raise FileExistsError(run_root)
    original_root.mkdir(parents=True)
    if run_root.stat().st_dev != root.stat().st_dev:
        raise RuntimeError("CLEARUP moet op hetzelfde filesystem staan voor een harde rename.")

    moved: list[tuple[Path, Path, dict[str, Any]]] = []
    manifest_items: list[dict[str, Any]] = []
    try:
        clearup_items = [item for item in fresh["items"] if item["disposition"] == "CLEARUP"]
        for index, item in enumerate(clearup_items, 1):
            _check_deadline(deadline_monotonic, "candidate_hash", candidate=item["source_path"])
            _emit_progress(
                progress_callback, phase="candidate_hash", started_monotonic=started_monotonic,
                candidate=item["source_path"], candidate_index=index, candidate_total=len(clearup_items), stage="pre_move",
            )
            source = root / item["source_path"]
            if _is_protected(item["source_path"]):
                raise RuntimeError(f"Protected path mocht niet in CLEARUP-plan staan: {item['source_path']}")
            if not source.exists() and not source.is_symlink():
                raise RuntimeError(f"CLEARUP-bron verdwenen vóór move: {item['source_path']}")
            if source.stat().st_dev != root.stat().st_dev:
                raise RuntimeError(f"Cross-filesystem CLEARUP geblokkeerd: {item['source_path']}")
            before_hash = _tree_sha256_runtime(
                source, deadline_monotonic=deadline_monotonic, phase="candidate_hash", candidate=item["source_path"]
            )
            if before_hash != item["tree_sha256"]:
                raise RuntimeError(f"CLEARUP-bron gewijzigd na plan: {item['source_path']}")
            # A rename on the same filesystem preserves the inode.  Capture
            # lstat identity before moving so destination integrity can be
            # verified without reading the entire tree a third/fourth time.
            before_stat = source.lstat()
            destination = original_root / item["source_path"]
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            moved.append((source, destination, item))
            if os.path.lexists(source):
                raise RuntimeError(f"Oud pad bestaat nog na harde CLEARUP-move: {item['source_path']}")
            if not destination.exists() and not destination.is_symlink():
                raise RuntimeError(f"CLEARUP-bestemming ontbreekt na move: {item['source_path']}")
            after_stat = destination.lstat()
            if (after_stat.st_dev, after_stat.st_ino, after_stat.st_size) != (
                before_stat.st_dev, before_stat.st_ino, before_stat.st_size
            ):
                raise RuntimeError(f"CLEARUP rename-identiteit wijkt af na move: {item['source_path']}")
            manifest_items.append({
                **item,
                "quarantine_path": _rel(destination, root),
                "tree_sha256": before_hash,
                "rename_identity_verified": True,
                "old_path_absent": True,
                "restore_status": "AVAILABLE",
                "moved_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        # Best-effort transaction rollback: never leave an unmanifested partial run.
        for source, destination, _ in reversed(moved):
            try:
                if not os.path.lexists(source) and (destination.exists() or destination.is_symlink()):
                    source.parent.mkdir(parents=True, exist_ok=True)
                    destination.rename(source)
            except OSError:
                pass
        raise

    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_version": fresh["current_version"],
        "plan_id": fresh["plan_id"],
        "prerequisite_fingerprint": fresh.get("prerequisite_fingerprint"),
        "hard_move": True,
        "symlinks_created": False,
        "delete_capability": False,
        "items": manifest_items,
        "review_items": [item for item in fresh["items"] if item["disposition"] == "REVIEW"],
    }
    _check_deadline(deadline_monotonic, "manifest")
    _write_json_atomic(run_root / "manifest.json", manifest)
    _emit_progress(
        progress_callback, phase="manifest", started_monotonic=started_monotonic,
        manifest=_rel(run_root / "manifest.json", root), moved_count=len(manifest_items),
        review_count=len(manifest["review_items"]),
    )
    return {
        "status": "completed",
        "run_id": run_id,
        "manifest": _rel(run_root / "manifest.json", root),
        "moved_count": len(manifest_items),
        "review_count": len(manifest["review_items"]),
        "delete_performed": False,
    }


def restore_clearup_run(project_root: Path, run_id: str, *, confirmation: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_id = _safe_run_id(run_id)
    if confirmation != f"RESTORE CLEARUP {run_id}":
        raise ValueError(f"Bevestiging ongeldig. Verwacht exact: RESTORE CLEARUP {run_id}")
    manifest_path = root / "CLEARUP" / run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA or manifest.get("run_id") != run_id:
        raise RuntimeError("Ongeldig CLEARUP-manifest")
    entries = list(manifest.get("items") or [])

    # Full preflight before moving anything: one conflict blocks the entire restore.
    for entry in entries:
        source = root / str(entry["quarantine_path"])
        target = root / str(entry["source_path"])
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        if not source.exists() and not source.is_symlink():
            raise FileNotFoundError(source)
        if tree_sha256(source) != entry.get("tree_sha256"):
            raise RuntimeError(f"CLEARUP restore hash mismatch: {entry['source_path']}")
        if source.stat().st_dev != root.stat().st_dev:
            raise RuntimeError(f"Cross-filesystem restore geblokkeerd: {entry['source_path']}")

    restored: list[tuple[Path, Path, dict[str, Any]]] = []
    try:
        for entry in entries:
            source = root / str(entry["quarantine_path"])
            target = root / str(entry["source_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            restored.append((source, target, entry))
            if os.path.lexists(source):
                raise RuntimeError(f"Quarantainepad bestaat nog na restore: {entry['quarantine_path']}")
            if tree_sha256(target) != entry.get("tree_sha256"):
                raise RuntimeError(f"Restore eindhash wijkt af: {entry['source_path']}")
    except Exception:
        for source, target, _ in reversed(restored):
            try:
                if not os.path.lexists(source) and (target.exists() or target.is_symlink()):
                    source.parent.mkdir(parents=True, exist_ok=True)
                    target.rename(source)
            except OSError:
                pass
        raise

    for entry in entries:
        entry["restore_status"] = "RESTORED"
        entry["restored_at"] = datetime.now(timezone.utc).isoformat()
    manifest["restored_at"] = datetime.now(timezone.utc).isoformat()
    _write_json_atomic(manifest_path, manifest)
    return {"status": "completed", "run_id": run_id, "restored_count": len(entries)}
