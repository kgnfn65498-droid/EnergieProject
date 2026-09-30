import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_delivery import build_delivery_receipt


def _package():
    return {
        "package_sha256": "a" * 64,
        "compiler_version": "test",
        "mandatory_context_complete": True,
        "resume_contract": {"fail_closed": False},
        "mandatory_sources": [{"path": "a.md", "sha256": "b" * 64}],
        "mandatory_requirements": [{"path": "r.md", "sha256": "c" * 64}],
        "deferred_requirement_refs": [{"path": "later.md"}],
        "optional_evidence_errors": [],
    }


def test_receipt_requires_real_invocation_binding():
    receipt = build_delivery_receipt(_package(), invocation_id="", final_input_sha256="d" * 64, consumer="chat")
    assert receipt["delivery_recorded"] is False


def test_receipt_requires_valid_final_input_hash():
    receipt = build_delivery_receipt(_package(), invocation_id="inv-1", final_input_sha256="not-a-hash", consumer="chat")
    assert receipt["delivery_recorded"] is False


def test_receipt_records_package_and_source_hashes_when_bound():
    receipt = build_delivery_receipt(_package(), invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat")
    assert receipt["delivery_recorded"] is True
    assert receipt["package_sha256"] == "a" * 64
    assert receipt["final_input_sha256"] == "d" * 64
    assert [x["path"] for x in receipt["source_hashes"]] == ["a.md", "r.md"]
    assert len(receipt["receipt_sha256"]) == 64


def test_fail_closed_package_cannot_claim_delivery():
    package = _package()
    package["resume_contract"]["fail_closed"] = True
    receipt = build_delivery_receipt(package, invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chat")
    assert receipt["delivery_recorded"] is False
