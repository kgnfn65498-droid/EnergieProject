from __future__ import annotations

"""Canonical release artifact builder.

Builds a release ZIP from source while filtering runtime/test cache and then
runs the same ZIP-member safety gate used by ``atomic_app_swap``.  MANIFEST and
SHA256SUMS are regenerated from the exact payload bytes that go into the ZIP.
"""

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from atomic_app_swap import _is_forbidden_release_path, _safe_zip_infos

_GENERATED_METADATA = {"MANIFEST.sha256", "SHA256SUMS.json"}
_EXCLUDED_DIR_PARTS = {".git"}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _filtered_release_path(relative: Path) -> bool:
    return (
        _is_forbidden_release_path(relative)
        or any(part in _EXCLUDED_DIR_PARTS for part in relative.parts)
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
        "payload_count": len(payload),
        "filtered_count": len(filtered),
        "filtered": filtered,
    }
