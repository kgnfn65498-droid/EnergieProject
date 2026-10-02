from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "energie_pm_context_package_v4"
COMPILER_VERSION = "2026-09-30.v4"
MAX_PACKAGE_BYTES = 48_000
MAX_MANDATORY_PASSAGE_CHARS = 4_000
MAX_EVIDENCE_ITEMS = 8
MAX_EVIDENCE_SNIPPET_CHARS = 900

_ALWAYS = {
    "HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
    "HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
    "HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
    "HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
    "HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
    "HARD_REQUIREMENT_NO_USER_TERMINAL.md",
}
_SCOPE_RULES = {
    "clearup": ("CLEARUP", "CAPABILITY_CONTINUITY", "DANGEROUS_COMMAND", "COMMAND_PROOF"),
    "cleanup": ("CLEARUP", "CAPABILITY_CONTINUITY", "DANGEROUS_COMMAND", "COMMAND_PROOF"),
    "capability": ("CAPABILITY_CONTINUITY", "MCP_TOOL_EXPOSURE"),
    "mcp": ("MCP_TOOL_EXPOSURE", "CAPABILITY_CONTINUITY"),
    "handover": ("ALWAYS_CURRENT_HANDOVER", "NEW_CHAT", "LIVE_HANDOVER"),
    "verder": ("NEW_CHAT", "ALWAYS_CURRENT_HANDOVER", "DEVELOPMENT_CONTINUITY"),
    "resume": ("NEW_CHAT", "ALWAYS_CURRENT_HANDOVER", "DEVELOPMENT_CONTINUITY"),
    "release": ("LIVE_RUNTIME_ACTIVATION", "NO_SPLIT_STATE", "RELEASE"),
    "recovery": ("RECOVERY", "DANGEROUS_COMMAND", "NO_USER_TERMINAL"),
    "terminal": ("NO_USER_TERMINAL", "DANGEROUS_COMMAND", "COMMAND_PROOF"),
    "index": ("NEW_CHAT", "UNIFIED_DEVELOPMENT_LEDGER", "PROACTIVE_PM_KB_HANDOVER_TRUTH"),
    "knowledge": ("NEW_CHAT", "UNIFIED_DEVELOPMENT_LEDGER", "PROACTIVE_PM_KB_HANDOVER_TRUTH", "DS9", "SPOCK", "FULL_KB", "FULLKB", "PROJECTMANAGER"),
    "projectmanager": ("PROJECTMANAGER", "DS9", "SPOCK", "FULL_KB", "FULLKB", "NEW_CHAT", "UNIFIED_DEVELOPMENT_LEDGER"),
    "context": ("NEW_CHAT", "HANDOVER", "FULL_KB", "FULLKB", "DEVELOPMENT_CONTINUITY"),
    "32.5.30": ("32_5_30", "PERSISTENT_NAS_TEST_ROUTE", "AUTONOMOUS_UNTIL_VERIFIED_ZIP"),
}
_NORMATIVE = (
    "harde regel", "verplicht", "verboden", "altijd", "fail closed", "fail-closed",
    "veiligheid", "acceptance", "hervatten", "nieuwe chat", "verder", "doel",
)
_EVIDENCE_ROOTS = (
    "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons",
    "Data/02_Output/Rapportages/KnowledgeBase",
)
_EVIDENCE_FILES = (
    "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/02_DECISION_LOG.md",
    "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/03_DEVELOPMENT_CHANGELOG.md",
    "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/05_TICKET_ISSUE_INDEX.md",
)

_HOT_LESSON_ROOT = "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons"
MAX_BINDING_HOT_LESSONS = 4


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read(root: Path, relative: str, *, with_text: bool = False) -> dict[str, Any]:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        return {"path": relative, "status": "MISSING", "sha256": "", "bytes": 0, "text": "" if with_text else None}
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": relative, "status": "UNREADABLE", "sha256": "", "bytes": 0, "error": type(exc).__name__, "text": "" if with_text else None}
    status = "GREEN" if data.strip() else "EMPTY"
    result = {"path": relative, "status": status, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if with_text:
        try:
            result["text"] = data.decode("utf-8")
        except UnicodeDecodeError:
            result["status"] = "UNREADABLE"
            result["text"] = ""
    return result


def _words(value: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", str(value or "").lower()) if len(w) >= 4}


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(part) for part in str(value or "").split("."))
    except ValueError:
        return ()
    return parts if len(parts) == 3 else ()


def _scope_needles(task_text: str) -> set[str]:
    lowered = task_text.lower()
    needles: set[str] = set()
    for key, scopes in _SCOPE_RULES.items():
        if key in lowered:
            needles.update(scopes)
    return needles


def _managed_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    start: int | None = None
    marker = ""
    for index, line in enumerate(lines):
        if "<!-- " in line and ":BEGIN -->" in line:
            start = index
            marker = line.split(":BEGIN -->", 1)[0]
            continue
        if start is not None and marker and line.startswith(marker) and ":END -->" in line:
            blocks.append("\n".join(lines[start:index + 1]).strip())
            start = None
            marker = ""
    return blocks


def _normative_passage(text: str) -> tuple[str, bool]:
    if not text.strip():
        return "", False
    managed = _managed_blocks(text)
    if managed:
        # Managed blocks are evidence only. Prefer the newest/current blocks at the
        # top of canonically maintained files; never infer whole-document truth.
        value = "\n\n".join(managed[:2]).strip()
    else:
        sections: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("#") and current:
                sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        selected = [section for section in sections if any(marker in section.lower() for marker in _NORMATIVE)]
        if not selected and sections:
            selected = sections[:1]
        value = "\n\n".join(selected).strip()
    truncated = len(value) > MAX_MANDATORY_PASSAGE_CHARS
    return value[:MAX_MANDATORY_PASSAGE_CHARS], truncated


def _validate_supersession_edges(edges: Any) -> list[dict[str, Any]]:
    """Validate optional explicit supersession metadata without inventing authority.

    Each edge is {"source": <id>, "supersedes": <id>}. Cycles, self-links and
    contradictory duplicate source claims fail closed. Absence of metadata is
    allowed; documents themselves never become governing merely by being newer.
    """
    if edges in (None, []):
        return []
    if not isinstance(edges, list):
        return [{"kind": "supersession_metadata_invalid"}]
    graph: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    for row in edges:
        if not isinstance(row, dict):
            conflicts.append({"kind": "supersession_edge_invalid"})
            continue
        source = str(row.get("source") or "").strip()
        target = str(row.get("supersedes") or "").strip()
        if not source or not target:
            conflicts.append({"kind": "supersession_edge_incomplete", "source": source, "supersedes": target})
            continue
        if source == target:
            conflicts.append({"kind": "supersession_self_cycle", "source": source})
            continue
        previous = graph.get(source)
        if previous and previous != target:
            conflicts.append({"kind": "supersession_contradiction", "source": source, "targets": sorted({previous, target})})
            continue
        graph[source] = target
    for start in sorted(graph):
        seen: set[str] = set()
        node = start
        while node in graph:
            if node in seen:
                conflicts.append({"kind": "supersession_cycle", "source": start, "at": node})
                break
            seen.add(node)
            node = graph[node]
    unique = []
    fingerprints = set()
    for item in conflicts:
        fp = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if fp not in fingerprints:
            fingerprints.add(fp)
            unique.append(item)
    return unique


def _binding_hot_lessons(root: Path, task_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = root / _HOT_LESSON_ROOT
    if not base.is_dir() or base.is_symlink():
        return [], [{"path": _HOT_LESSON_ROOT, "reason": "hot_lesson_root_missing"}]
    terms = _words(task_text)
    candidates: list[tuple[int, str, Path, str]] = []
    errors: list[dict[str, Any]] = []
    try:
        paths = sorted(p for p in base.glob("*.md") if p.is_file() and not p.is_symlink())
    except OSError as exc:
        return [], [{"path": _HOT_LESSON_ROOT, "reason": type(exc).__name__}]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append({"path": path.relative_to(root).as_posix(), "reason": type(exc).__name__})
            continue
        head = "\n".join(text.splitlines()[:24]).lower()
        if "status:" not in head or "hot" not in head:
            continue
        relative = path.relative_to(root).as_posix()
        hay = (path.name + "\n" + text).lower()
        hits = [term for term in terms if term in hay]
        if terms and not hits:
            continue
        score = sum(hay.count(term) for term in hits) if hits else 1
        candidates.append((score, relative, path, text))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected: list[dict[str, Any]] = []
    for score, relative, _path, text in candidates[:MAX_BINDING_HOT_LESSONS]:
        truncated = len(text) > MAX_MANDATORY_PASSAGE_CHARS
        passage = text[:MAX_MANDATORY_PASSAGE_CHARS]
        selected.append({
            "path": relative,
            "status": "GREEN" if text.strip() else "EMPTY",
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "bytes": len(text.encode("utf-8")),
            "selection_reason": ["binding_hot", "lexical_task_match"],
            "authority": "binding_hot_lesson",
            "score": score,
            "passage": passage,
            "passage_sha256": hashlib.sha256(passage.encode("utf-8")).hexdigest() if passage else "",
            "passage_truncated": truncated,
        })
    return selected, errors


def _select_requirements(root: Path, requirements: list[str], task_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    discovered = {Path(p).name: p for p in requirements}
    missing_always = sorted(name for name in _ALWAYS if name not in discovered)
    scopes = _scope_needles(task_text)
    task_words = _words(task_text)
    mandatory: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for name, relative in sorted(discovered.items()):
        upper = name.upper()
        reasons: list[str] = []
        if name in _ALWAYS:
            reasons.append("always")
        reasons.extend("scope:" + scope for scope in sorted(scopes) if scope in upper)
        if task_words.intersection(_words(name)):
            reasons.append("lexical")
        if reasons:
            item = _read(root, relative, with_text=True)
            passage, passage_truncated = _normative_passage(str(item.pop("text", "") or ""))
            item["selection_reason"] = sorted(set(reasons))
            item["authority"] = "binding_requirement"
            item["passage"] = passage
            item["passage_sha256"] = hashlib.sha256(passage.encode("utf-8")).hexdigest() if passage else ""
            item["passage_truncated"] = passage_truncated
            mandatory.append(item)
        else:
            deferred.append(_read(root, relative, with_text=False))
    return mandatory, deferred, missing_always


def _lexical_evidence(root: Path, task_text: str, *, exclude: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    terms = _words(task_text)
    if not terms:
        return [], []
    candidates: list[tuple[int, str, str, str]] = []
    errors: list[dict[str, Any]] = []
    paths: list[Path] = []
    for relative in _EVIDENCE_ROOTS:
        base = root / relative
        if base.is_dir() and not base.is_symlink():
            try:
                paths.extend(p for p in base.rglob("*.md") if p.is_file() and not p.is_symlink())
            except OSError as exc:
                errors.append({"path": relative, "reason": type(exc).__name__})
    for relative in _EVIDENCE_FILES:
        p = root / relative
        if p.is_file() and not p.is_symlink():
            paths.append(p)
    if {"clearup", "cleanup"}.intersection(terms):
        p = root / "Data/03_Systeem/Projectmanager/CLEARUP_OPERATIONS_PLAYBOOK_32_5.md"
        if p.is_file() and not p.is_symlink():
            paths.append(p)

    seen: set[str] = set()
    for path in paths:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative in exclude or relative in seen:
            continue
        seen.add(relative)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append({"path": relative, "reason": type(exc).__name__})
            continue
        lowered = text.lower()
        hits = [term for term in terms if term in lowered]
        if not hits:
            continue
        score = sum(lowered.count(term) for term in hits)
        pos = min((lowered.find(term) for term in hits if lowered.find(term) >= 0), default=0)
        start = max(0, pos - 180)
        snippet = text[start:start + MAX_EVIDENCE_SNIPPET_CHARS].strip()
        candidates.append((score, relative, hashlib.sha256(text.encode("utf-8")).hexdigest(), snippet))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return (
        [{"path": rel, "sha256": sha, "score": score, "snippet": snippet, "authority": "supporting_evidence"} for score, rel, sha, snippet in candidates[:MAX_EVIDENCE_ITEMS]],
        errors,
    )


def _issue_evidence(root: Path, task_text: str) -> list[dict[str, Any]]:
    terms = _words(task_text)
    path = root / "Data/03_Systeem/Projectmanager/RuntimeV2/issues/issues.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    rows = payload.get("items") if isinstance(payload, dict) else []
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        hay = " ".join(str(row.get(k) or "") for k in ("fingerprint", "title", "resolution", "details")).lower()
        if terms and not any(term in hay for term in terms):
            continue
        result.append({
            "fingerprint": row.get("fingerprint"),
            "status": row.get("status"),
            "title": row.get("title"),
            "resolution": row.get("resolution"),
            "authority": "supporting_evidence",
        })
        if len(result) >= 5:
            break
    return result


def _capability_evidence(capabilities: dict[str, Any], task_text: str) -> list[dict[str, Any]]:
    terms = _words(task_text)
    rows = capabilities.get("capabilities") if isinstance(capabilities, dict) else []
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        hay = " ".join(str(row.get(k) or "") for k in ("key", "executor", "reason")).lower()
        if terms and not any(term in hay for term in terms):
            continue
        result.append({
            "key": row.get("key"),
            "status": row.get("status"),
            "executor": row.get("executor"),
            "files_present": row.get("files_present"),
            "reason": row.get("reason"),
            "authority": "capability_registry",
        })
    return result[:8]


def compact_package(package: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(package, dict):
        return {}
    return {
        "schema": package.get("schema"),
        "compiler_version": package.get("compiler_version"),
        "package_sha256": package.get("package_sha256"),
        "inventory_complete": package.get("inventory_complete") is True,
        "mandatory_context_complete": package.get("mandatory_context_complete") is True,
        "current_truth": package.get("current_truth") or {},
        "active_task": package.get("active_task") or {},
        "resume_contract": package.get("resume_contract") or {},
        "mandatory_source_refs": [
            {k: item.get(k) for k in ("path", "status", "sha256", "bytes", "selection_reason", "passage_sha256", "passage_truncated", "authority")}
            for item in (package.get("mandatory_sources") or []) if isinstance(item, dict)
        ],
        "mandatory_requirement_refs": [
            {k: item.get(k) for k in ("path", "status", "sha256", "bytes", "selection_reason", "passage_sha256", "authority")}
            for item in (package.get("mandatory_requirements") or []) if isinstance(item, dict)
        ],
        "binding_hot_lesson_refs": [
            {k: item.get(k) for k in ("path", "status", "sha256", "bytes", "selection_reason", "passage_sha256", "authority")}
            for item in (package.get("binding_hot_lessons") or []) if isinstance(item, dict)
        ],
        "conflicts_missing_evidence": package.get("conflicts_missing_evidence") or {},
        "delivery_status": "UNPROVEN",
        "behavior_status": "UNPROVEN",
    }


def build_context_package(
    project_root: Path | str,
    *,
    status: dict[str, Any],
    source_paths: dict[str, str],
    requirements: list[str],
    full_kb: dict[str, Any],
    truth: dict[str, Any],
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    active = status.get("active_task") if isinstance(status.get("active_task"), dict) else {}
    task_text = " ".join(str(active.get(k) or "") for k in ("title", "goal", "next_action"))
    mandatory_requirements, deferred_requirements, missing_registry = _select_requirements(root, requirements, task_text)

    core_names = ("master_index", "active_context", "manifest", "ledger_current_truth", "spock_context", "current_handover")
    missing_source_keys = [name for name in core_names if not source_paths.get(name)]
    core_sources = []
    for name in core_names:
        if not source_paths.get(name):
            continue
        item = _read(root, source_paths[name], with_text=True)
        passage, passage_truncated = _normative_passage(str(item.pop("text", "") or ""))
        item["selection_reason"] = ["mandatory_core:" + name]
        item["authority"] = "supporting_evidence"
        item["passage"] = passage
        item["passage_sha256"] = hashlib.sha256(passage.encode("utf-8")).hexdigest() if passage else ""
        item["passage_truncated"] = passage_truncated
        core_sources.append(item)

    binding_hot_lessons, hot_errors = _binding_hot_lessons(root, task_text)
    invalid = [
        x["path"] for x in core_sources + mandatory_requirements + binding_hot_lessons
        if x.get("status") != "GREEN" or not str(x.get("passage") or "").strip() or x.get("passage_truncated") is True
    ]
    invalid.extend("requirement:" + name for name in missing_registry)
    invalid.extend("source_key:" + name for name in missing_source_keys)
    invalid.extend("binding_hot:" + str(item.get("path") or item.get("reason") or "unknown") for item in hot_errors)

    conflicts = list(truth.get("conflicts") or [])
    conflicts.extend(_validate_supersession_edges(truth.get("supersession_edges")))
    first_action = str(truth.get("first_unproven_action") or active.get("next_action") or status.get("next_action") or "").strip()
    if not active or not first_action:
        invalid.append("active_task:first_unproven_action")

    self_audit = status.get("self_audit") if isinstance(status.get("self_audit"), dict) else {}
    self_audit_status = str(self_audit.get("status") or "").strip().upper()
    if self_audit_status == "RED":
        conflicts.append({"kind": "projectmanager_self_audit_red", "invalid": list(self_audit.get("invalid") or [])})
    elif self_audit_status not in {"GREEN", "ORANGE"}:
        conflicts.append({"kind": "projectmanager_self_audit_missing_or_invalid"})

    governing_claims = truth.get("governing_claims") if isinstance(truth.get("governing_claims"), dict) else {}
    artifact_path = str(governing_claims.get("artifact") or "").strip()
    artifact_sha = str(governing_claims.get("artifact_sha256") or "").strip().lower()
    artifact_size_raw = governing_claims.get("artifact_size")
    try:
        artifact_size = int(artifact_size_raw) if artifact_size_raw not in (None, "") else None
    except (TypeError, ValueError):
        artifact_size = None
    target_release = str(governing_claims.get("target_release") or "").strip()
    artifact_identity = {
        "path": artifact_path,
        "sha256": artifact_sha,
        "bytes": artifact_size,
        "authority": "governing_artifact",
    }
    if _version_tuple(target_release) >= (32, 5, 30):
        if not artifact_path:
            invalid.append("artifact_identity:path_missing")
        if len(artifact_sha) != 64 or any(ch not in "0123456789abcdef" for ch in artifact_sha):
            invalid.append("artifact_identity:sha256_invalid")
        if artifact_size is None or artifact_size <= 0:
            invalid.append("artifact_identity:size_missing")
        if artifact_path:
            artifact_file = root / artifact_path
            if artifact_file.is_symlink() or not artifact_file.is_file():
                invalid.append("artifact_identity:file_missing_or_unsafe")
            elif artifact_size is not None:
                try:
                    if artifact_file.stat().st_size != artifact_size:
                        invalid.append("artifact_identity:size_mismatch")
                except OSError:
                    invalid.append("artifact_identity:stat_failed")

    complete = bool(
        full_kb.get("complete") is True
        and not invalid
        and not conflicts
        and truth.get("status") == "GREEN"
        and truth.get("fail_closed") is not True
    )
    checkpoint = full_kb.get("checkpoint") if isinstance(full_kb.get("checkpoint"), dict) else {}
    exclude = {str(x.get("path") or "") for x in core_sources + mandatory_requirements}
    evidence, evidence_errors = _lexical_evidence(root, task_text, exclude=exclude)
    evidence_errors.extend(hot_errors)

    package = {
        "schema": SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "inventory_complete": full_kb.get("complete") is True,
        "mandatory_context_complete": complete,
        "authority_contract": {
            "governing_truth": "live_runtime_plus_highest_valid_checkpoint",
            "requirements": "binding_when_selected",
            "documents": "supporting_evidence_only",
            "history": "never_governing_without_explicit_current_promotion",
        },
        "current_truth": {
            "live_release": truth.get("live_release") or str((status.get("release") or {}).get("version") or ""),
            "highest_checkpoint": checkpoint.get("path") or truth.get("highest_checkpoint") or "",
            "truth_status": truth.get("status"),
            "governing_claims": governing_claims,
        },
        "artifact_identity": artifact_identity,
        "active_task": {
            "id": active.get("id"),
            "title": active.get("title"),
            "status": active.get("status"),
            "step": active.get("step"),
            "steps_total": active.get("steps_total"),
            "first_unproven_action": first_action,
            "blockers": list(active.get("blockers") or []),
        },
        "mandatory_sources": core_sources,
        "mandatory_requirements": mandatory_requirements,
        "binding_hot_lessons": binding_hot_lessons,
        "task_evidence": evidence,
        "known_issue_evidence": _issue_evidence(root, task_text),
        "capability_evidence": _capability_evidence(capabilities or {}, task_text),
        "optional_evidence_errors": evidence_errors,
        "deferred_requirement_refs": deferred_requirements,
        "deferred_evidence": [],
        "forbidden_shortcuts": [
            "do_not_treat_history_as_current_truth",
            "do_not_repeat_proven_work_without_invalidating_evidence",
            "do_not_replace_mandatory_core_with_retrieval",
            "do_not_create_parallel_truth_store",
            "do_not_claim_delivery_without_invocation_bound_receipt",
        ],
        "conflicts_missing_evidence": {"conflicts": conflicts, "missing": sorted(set(invalid))},
        "resume_contract": {
            "command": "verder",
            "deterministic": complete,
            "first_unproven_action": first_action,
            "broad_history_scan_default": False,
            "fail_closed": not complete,
        },
        "delivery_status": "UNPROVEN",
        "behavior_status": "UNPROVEN",
    }

    while len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES and package["task_evidence"]:
        item = package["task_evidence"].pop()
        package["deferred_evidence"].append({"collection": "task_evidence", "identity": item.get("path"), "reason": "context_budget"})
    while len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES and package["known_issue_evidence"]:
        item = package["known_issue_evidence"].pop()
        package["deferred_evidence"].append({"collection": "known_issue_evidence", "identity": item.get("fingerprint") or item.get("title"), "reason": "context_budget"})
    while len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES and package["capability_evidence"]:
        item = package["capability_evidence"].pop()
        package["deferred_evidence"].append({"collection": "capability_evidence", "identity": item.get("key"), "reason": "context_budget"})
    if len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES:
        package["optional_evidence_errors"].append({"reason": "optional_context_budget_exceeded"})

    package["package_sha256"] = _canonical_sha(package)
    package["package_bytes"] = len(_canonical_bytes(package))
    return package
