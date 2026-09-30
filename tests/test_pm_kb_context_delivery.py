import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_delivery import build_delivery_receipt


def _package(tmp_path):
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "r.md").write_text("r", encoding="utf-8")
    return {
        "package_sha256": "a" * 64,
        "compiler_version": "test",
        "mandatory_context_complete": True,
        "resume_contract": {"fail_closed": False},
        "mandatory_sources": [{"path": "a.md", "sha256": hashlib.sha256(b"a").hexdigest()}],
        "mandatory_requirements": [{"path": "r.md", "sha256": hashlib.sha256(b"r").hexdigest()}],
        "deferred_requirement_refs": [{"path": "later.md"}],
        "optional_evidence_errors": [],
    }


def test_receipt_requires_real_invocation_binding(tmp_path):
    receipt = build_delivery_receipt(_package(tmp_path), invocation_id="", final_input_sha256="d" * 64, consumer="chat", project_root=tmp_path)
    assert receipt["delivery_recorded"] is False


def test_receipt_requires_valid_final_input_hash(tmp_path):
    receipt = build_delivery_receipt(_package(tmp_path), invocation_id="inv-1", final_input_sha256="not-a-hash", consumer="chat", project_root=tmp_path)
    assert receipt["delivery_recorded"] is False


def test_receipt_requires_project_root_source_revalidation(tmp_path):
    receipt = build_delivery_receipt(_package(tmp_path), invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat")
    assert receipt["delivery_recorded"] is False
    assert receipt["source_validation"]["status"] == "UNPROVEN"


def test_receipt_records_package_and_source_hashes_when_bound(tmp_path):
    receipt = build_delivery_receipt(_package(tmp_path), invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat", project_root=tmp_path)
    assert receipt["delivery_recorded"] is True
    assert receipt["package_sha256"] == "a" * 64
    assert receipt["final_input_sha256"] == "d" * 64
    assert [x["path"] for x in receipt["source_hashes"]] == ["a.md", "r.md"]
    assert len(receipt["receipt_sha256"]) == 64


def test_source_change_after_package_invalidates_delivery(tmp_path):
    package = _package(tmp_path)
    (tmp_path / "a.md").write_text("changed", encoding="utf-8")
    receipt = build_delivery_receipt(package, invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat", project_root=tmp_path)
    assert receipt["delivery_recorded"] is False
    assert any(x.get("reason") == "source_hash_changed" for x in receipt["source_validation"]["mismatches"])


def test_fail_closed_package_cannot_claim_delivery(tmp_path):
    package = _package(tmp_path)
    package["resume_contract"]["fail_closed"] = True
    receipt = build_delivery_receipt(package, invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat", project_root=tmp_path)
    assert receipt["delivery_recorded"] is False
