from pathlib import Path
import sys

PM = Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_package import build_context_package

def _write(root, relative, text="ok"):
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def _fixture(tmp_path):
    paths = {
        "master_index": "kb/00_MASTER_DEVELOPMENT_INDEX.md",
        "active_context": "kb/00_ACTIVE_DEVELOPMENT_CONTEXT.md",
        "ledger_current_truth": "kb/01A_LEDGER_CURRENT_TRUTH.md",
        "spock_context": "kb/04_SPOCK_CONTEXT.md",
        "current_handover": "handover/CURRENT_DEVELOPMENT_HANDOVER.md",
    }
    for p in paths.values():
        _write(tmp_path, p)
    reqs = [
        "requirements/HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
        "requirements/HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
        "requirements/HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
        "requirements/HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
        "requirements/HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
        "requirements/HARD_REQUIREMENT_NO_USER_TERMINAL.md",
        "requirements/HARD_REQUIREMENT_CLEARUP_END_TO_END_EXECUTION_PROOF.md",
    ]
    for p in reqs:
        _write(tmp_path, p, p)
    status = {
        "release": {"version": "9.9.9"},
        "active_task": {"id": "t1", "title": "index", "status": "ACTIVE", "next_action": "continue index work", "blockers": []},
    }
    full = {"complete": True, "checkpoint": {"path": "checkpoint.json"}}
    truth = {"status": "GREEN", "fail_closed": False, "live_release": "9.9.9", "conflicts": []}
    return paths, reqs, status, full, truth

def test_mandatory_core_is_complete_and_history_is_deferred(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["inventory_complete"] is True
    assert pkg["mandatory_context_complete"] is True
    assert pkg["resume_contract"]["command"] == "verder"
    assert pkg["resume_contract"]["first_unproven_action"] == "continue index work"
    mandatory = {Path(x["path"]).name for x in pkg["mandatory_requirements"]}
    assert "HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md" in mandatory
    assert "HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md" in mandatory
    assert any(Path(x["path"]).name == "HARD_REQUIREMENT_CLEARUP_END_TO_END_EXECUTION_PROOF.md" for x in pkg["deferred_requirement_refs"])

def test_missing_mandatory_source_fails_closed(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    (tmp_path / paths["active_context"]).unlink()
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True
    assert paths["active_context"] in pkg["conflicts_missing_evidence"]["missing"]

def test_truth_conflict_fails_closed(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    truth["status"] = "RED"
    truth["fail_closed"] = True
    truth["conflicts"] = [{"kind": "test"}]
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True
    assert pkg["conflicts_missing_evidence"]["conflicts"] == [{"kind": "test"}]

def test_package_has_source_hashes(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert len(pkg["package_sha256"]) == 64
    assert all(len(x["sha256"]) == 64 for x in pkg["mandatory_sources"])


def test_missing_always_requirement_from_inventory_fails_closed(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    reqs = [p for p in reqs if not p.endswith("HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md")]
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert "requirement:HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md" in pkg["conflicts_missing_evidence"]["missing"]

def test_empty_source_map_fails_closed(tmp_path):
    _, reqs, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(tmp_path, status=status, source_paths={}, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True

def test_empty_mandatory_file_fails_closed(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    (tmp_path / paths["master_index"]).write_text("", encoding="utf-8")
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False

def test_missing_active_action_fails_closed(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    status["active_task"] = {}
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["deterministic"] is False

def test_clearup_scope_selects_clearup_requirement(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    status["active_task"]["title"] = "ClearUp capability check"
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    names = {Path(x["path"]).name for x in pkg["mandatory_requirements"]}
    assert "HARD_REQUIREMENT_CLEARUP_END_TO_END_EXECUTION_PROOF.md" in names

def test_context_package_contains_refs_not_full_source_text(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    huge = "x" * 1_500_000
    (tmp_path / paths["master_index"]).write_text(huge, encoding="utf-8")
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    import json
    encoded = json.dumps(pkg, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < 100_000
    assert len(pkg["mandatory_sources"][0]["passage"]) <= 4000
    assert pkg["mandatory_context_complete"] is False
    assert pkg["mandatory_sources"][0]["passage_truncated"] is True


def test_checkpoint_governing_action_wins_over_stale_active_action(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    truth["first_unproven_action"] = "checkpoint action"
    truth["governing_claims"] = {"first_unproven_action": "checkpoint action"}
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["active_task"]["first_unproven_action"] == "checkpoint action"
    assert pkg["resume_contract"]["first_unproven_action"] == "checkpoint action"

def test_red_self_audit_blocks_resume(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    status["self_audit"] = {"status": "RED", "invalid": [{"reason": "broken"}]}
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True

def test_package_hash_is_canonical_json_stable(tmp_path):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    a = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    b = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert a["package_sha256"] == b["package_sha256"]

def test_optional_evidence_io_failure_does_not_remove_mandatory_core(tmp_path, monkeypatch):
    paths, reqs, status, full, truth = _fixture(tmp_path)
    lesson = tmp_path / "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/lesson.md"
    lesson.parent.mkdir(parents=True, exist_ok=True)
    lesson.write_text("index useful evidence", encoding="utf-8")
    original = Path.read_text
    def flaky(self, *args, **kwargs):
        if self.name == "lesson.md":
            raise PermissionError("nope")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", flaky)
    pkg = build_context_package(tmp_path, status=status, source_paths=paths, requirements=reqs, full_kb=full, truth=truth)
    assert pkg["mandatory_context_complete"] is True
    assert pkg["optional_evidence_errors"]
