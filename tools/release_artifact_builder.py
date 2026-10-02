from __future__ import annotations

"""Canonical release artifact builder.

Builds a release ZIP from source while filtering runtime/test cache and then
runs the same ZIP-member safety gate used by ``atomic_app_swap``.  MANIFEST and
SHA256SUMS are regenerated from the exact payload bytes that go into the ZIP.
"""

import ast
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from atomic_app_swap import _is_forbidden_release_path, _safe_zip_infos

_GENERATED_METADATA = {"MANIFEST.sha256", "SHA256SUMS.json"}
_BUILD_EVIDENCE = {"fulltest.log", "fulltest.exit", ".energie-32530-workspace.json"}
_EXCLUDED_DIR_PARTS = {".git"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _python_constant(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in statement.targets):
            if not isinstance(statement.value, ast.Constant) or not isinstance(statement.value.value, str):
                raise ValueError(f"release identity {name} must be a string constant: {path}")
            return statement.value.value.strip()
    raise ValueError(f"release identity {name} missing: {path}")


_EXTENDED_IDENTITY_PATHS = (
    "slimmemeterportal_import/config.yaml",
    "slimmemeterportal_import/rootfs/app/main.py",
    "slimmemeterportal_import/rootfs/app/mode_entrypoint.py",
    "release_test_contract.py",
)


def _extended_identity_mode(source_root: Path) -> bool:
    present = [(source_root / relative).is_file() for relative in _EXTENDED_IDENTITY_PATHS]
    if any(present) and not all(present):
        missing = [
            relative for relative, exists in zip(_EXTENDED_IDENTITY_PATHS, present)
            if not exists
        ]
        raise ValueError("incomplete release identity contract: " + ", ".join(missing))
    return all(present)


def _verify_release_identity(source_root: Path) -> str:
    target = (source_root / "VERSIE.txt").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+(?:\.\d+){2}", target):
        raise ValueError(f"invalid VERSIE.txt release identity: {target!r}")

    # Historical packaging-unit fixtures intentionally model the older minimal
    # release contract. Current/full releases become strict as soon as any
    # extended identity file exists: partial extended identity is never accepted.
    if not _extended_identity_mode(source_root):
        return target

    config_text = (source_root / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^version:\s*[\"']?([^\"'\s]+)[\"']?\s*$", config_text)
    config_version = match.group(1).strip() if match else ""

    values = {
        "VERSIE.txt": target,
        "config.yaml": config_version,
        "main.APP_VERSION": _python_constant(
            source_root / "slimmemeterportal_import/rootfs/app/main.py", "APP_VERSION"
        ),
        "mode_entrypoint.TARGET_RELEASE_VERSION": _python_constant(
            source_root / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py", "TARGET_RELEASE_VERSION"
        ),
        "release_test_contract.CURRENT_RELEASE": _python_constant(
            source_root / "release_test_contract.py", "CURRENT_RELEASE"
        ),
    }
    mismatched = {name: value for name, value in values.items() if value != target}
    if mismatched:
        detail = ", ".join(f"{name}={value!r}" for name, value in mismatched.items())
        raise ValueError(f"release identity mismatch for target {target}: {detail}")
    return target


def _verify_release_chain_contract(source_root: Path) -> None:
    binding = source_root / "tools/github_publisher_binding.py"
    if not binding.is_file():
        if _extended_identity_mode(source_root):
            raise ValueError("release publisher binding missing")
        return
    tree = ast.parse(binding.read_text(encoding="utf-8"))
    has_system_path_import = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "system_path_contract"
        and any(alias.name == "project_system_path" for alias in statement.names)
        for statement in tree.body
    )
    if not has_system_path_import:
        raise ValueError("release publisher binding missing project_system_path import")



def _filtered_release_path(relative: Path) -> bool:
    return (
        _is_forbidden_release_path(relative)
        or any(part in _EXCLUDED_DIR_PARTS for part in relative.parts)
        or (len(relative.parts) == 1 and relative.name in _BUILD_EVIDENCE)
        or (len(relative.parts) == 1 and relative.name.startswith('.testfiles') and relative.suffix == '.txt')
    )


def _payload(source_root: Path) -> tuple[list[tuple[str, Path, str]], list[str]]:
    source_root = source_root.resolve()
    payload: list[tuple[str, Path, str]] = []
    filtered: list[str] = []
    for path in sorted(source_root.rglob("*"), key=lambda p: p.as_posix()):
        relative = path.relative_to(source_root)
        rel = relative.as_posix()
        if path.is_symlink():
            raise ValueError(f"release source symlink is forbidden: {rel}")
        if path.is_dir():
            continue
        if not path.is_file():
            continue
        if rel in _GENERATED_METADATA:
            continue
        if _filtered_release_path(relative):
            filtered.append(rel)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        payload.append((rel, path, digest))
    return payload, filtered


def _metadata(payload: list[tuple[str, Path, str]]) -> tuple[bytes, bytes]:
    manifest = "".join(f"{digest}  {rel}\n" for rel, _path, digest in payload).encode("utf-8")
    sums = json.dumps(
        {"files": [{"path": rel, "sha256": digest} for rel, _path, digest in payload]},
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    ).encode("utf-8") + b"\n"
    return manifest, sums


def _verify_exact_archive(path: Path, expected_payload: list[tuple[str, Path, str]]) -> None:
    expected = {rel: digest for rel, _source, digest in expected_payload}
    with zipfile.ZipFile(path, "r") as archive:
        infos = _safe_zip_infos(archive)
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"release ZIP CRC failure: {bad}")
        names = [info.filename for info in infos if not info.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("release ZIP contains duplicate members")
        for rel, digest in expected.items():
            actual = _sha256_bytes(archive.read(rel))
            if actual != digest:
                raise ValueError(f"release ZIP payload hash mismatch: {rel}")
        manifest_rows = archive.read("MANIFEST.sha256").decode("utf-8").splitlines()
        manifest_paths = {row.split(maxsplit=1)[1].strip() for row in manifest_rows if row.strip()}
        if manifest_paths != set(expected):
            raise ValueError("release manifest path set differs from exact payload")
        sums = json.loads(archive.read("SHA256SUMS.json"))
        json_map = {item["path"]: item["sha256"] for item in sums.get("files", [])}
        if json_map != expected:
            raise ValueError("SHA256SUMS.json differs from exact payload")


def build_release_artifact(source_root: Path | str, output_zip: Path | str) -> dict[str, Any]:
    source = Path(source_root).resolve()
    output = Path(output_zip).resolve()
    if not source.is_dir():
        raise ValueError(f"release source directory missing: {source}")
    release_identity = _verify_release_identity(source)
    _verify_release_chain_contract(source)
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        raise ValueError("release output must be outside the source tree")

    payload, filtered = _payload(source)
    required = {
        "README.md",
        "INSTALL.md",
        "CHANGELOG.md",
        "repository.yaml",
        "VERSIE.txt",
        "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt",
    }
    missing = sorted(required - {rel for rel, _path, _digest in payload})
    if missing:
        raise ValueError(f"required release source files missing: {', '.join(missing)}")

    manifest, sums = _metadata(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for rel, path, _digest in payload:
                archive.write(path, arcname=rel)
            archive.writestr("MANIFEST.sha256", manifest)
            archive.writestr("SHA256SUMS.json", sums)
        _verify_exact_archive(temp, payload)
        temp.replace(output)
    finally:
        if temp.exists():
            temp.unlink()

    artifact_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "status": "GREEN",
        "artifact": str(output),
        "artifact_sha256": artifact_sha,
        "release_identity": release_identity,
        "payload_count": len(payload),
        "filtered_count": len(filtered),
        "filtered": filtered,
    }
