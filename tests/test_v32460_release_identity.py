from __future__ import annotations

import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TARGET = "32.4.65"


def _module_value(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in statement.targets
        ):
            assert isinstance(statement.value, ast.Constant)
            return statement.value.value
    raise AssertionError(f"{name} missing from {path}")


def test_62_release_identity_is_coherent():
    contract = ROOT / "release_test_contract.py"
    release_contract = {}
    exec(contract.read_text(encoding="utf-8"), release_contract)

    assert release_contract["CURRENT_RELEASE"] == TARGET
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == TARGET
    assert yaml.safe_load((ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8"))["version"] == TARGET
    assert _module_value(ROOT / "slimmemeterportal_import/rootfs/app/main.py", "APP_VERSION") == TARGET
    assert _module_value(ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py", "TARGET_RELEASE_VERSION") == TARGET
    assert (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()[0] == f"## {TARGET} — consolidation, exact predecessor provenance and handover hygiene"
    assert (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8").splitlines()[0] == f"## {TARGET}"
