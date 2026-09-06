#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RecoveryRequired(RuntimeError):
    """Raised when persisted swap state and physical filesystem state disagree."""


@dataclass(frozen=True)
class SwapPaths:
    root: Path
    app: Path
    candidate: Path
    rollback: Path
    inbox: Path
    journal: Path
    lock: Path
    from_version: str
    to_version: str

    @classmethod
    def for_release(cls, root: Path, from_version: str, to_version: str) -> "SwapPaths":
        root = Path(root)
        inbox = root / "Inbox"
        return cls(
            root=root,
            app=root / "App",
            candidate=root / f"App.__candidate_{to_version}",
            rollback=root / f"App.__rollback_{from_version}",
            inbox=inbox,
            journal=inbox / "atomic_app_swap_state.json",
            lock=inbox / ".atomic_app_swap.lock",
            from_version=from_version,
            to_version=to_version,
        )


def write_journal_atomic(
    paths: SwapPaths,
    *,
    state: str,
    artifact_sha256: str,
    error: str = "",
) -> dict[str, Any]:
    paths.inbox.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "state": state,
        "from_version": paths.from_version,
        "to_version": paths.to_version,
        "artifact_sha256": artifact_sha256,
        "candidate_path": paths.candidate.name,
        "rollback_path": paths.rollback.name,
        "error": error,
    }

    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{paths.journal.name}.tmp.",
        dir=str(paths.inbox),
        text=True,
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fchmod(handle.fileno(), 0o644)
            os.fsync(handle.fileno())
        os.replace(tmp, paths.journal)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise
    return payload


def load_journal(paths: SwapPaths) -> dict[str, Any] | None:
    if not paths.journal.is_file():
        return None
    data = json.loads(paths.journal.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("atomic swap journal is not an object")
    return data


def acquire_swap_lock(paths: SwapPaths) -> None:
    paths.inbox.mkdir(parents=True, exist_ok=True)
    try:
        paths.lock.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"swap lock already exists: {paths.lock}") from exc


def release_swap_lock(paths: SwapPaths) -> None:
    try:
        paths.lock.rmdir()
    except FileNotFoundError:
        return


def _read_version(app_dir: Path) -> str | None:
    version_file = app_dir / "VERSIE.txt"
    if not version_file.is_file():
        return None
    return version_file.read_text(encoding="utf-8").strip()


def _require_version(app_dir: Path, expected: str, *, label: str) -> None:
    actual = _read_version(app_dir)
    if actual != expected:
        raise RecoveryRequired(f"{label} version mismatch: expected {expected}, got {actual!r}")


def reconcile_state(paths: SwapPaths) -> dict[str, Any]:
    journal = load_journal(paths)
    if journal is None:
        raise RecoveryRequired("atomic swap journal is missing")

    state = str(journal.get("state", ""))
    artifact_sha256 = str(journal.get("artifact_sha256", ""))

    if str(journal.get("from_version", "")) != paths.from_version:
        raise RecoveryRequired("journal source version does not match requested release")
    if str(journal.get("to_version", "")) != paths.to_version:
        raise RecoveryRequired("journal target version does not match requested release")

    if state == "PREPARED":
        _require_version(paths.app, paths.from_version, label="active App")
        if paths.rollback.exists():
            raise RecoveryRequired("PREPARED state unexpectedly has rollback directory")
        return journal

    if state == "OLD_RENAMED":
        if paths.app.exists():
            raise RecoveryRequired("OLD_RENAMED state unexpectedly still has active App")
        _require_version(paths.rollback, paths.from_version, label="rollback App")
        paths.rollback.rename(paths.app)
        return write_journal_atomic(
            paths,
            state="ROLLED_BACK",
            artifact_sha256=artifact_sha256,
            error="reconciled OLD_RENAMED by restoring source App",
        )

    if state in {"NEW_ACTIVE", "LIVE_ACCEPTANCE"}:
        actual = _read_version(paths.app)
        if actual != paths.to_version:
            raise RecoveryRequired(
                f"active App must contain target version {paths.to_version}, got {actual!r}"
            )
        _require_version(paths.rollback, paths.from_version, label="rollback App")
        return journal

    if state == "ROLLED_BACK":
        _require_version(paths.app, paths.from_version, label="active App")
        if paths.rollback.exists():
            raise RecoveryRequired("ROLLED_BACK state unexpectedly retains canonical rollback directory")
        return journal

    if state == "ACCEPTED":
        _require_version(paths.app, paths.to_version, label="active App")
        return journal

    raise RecoveryRequired(f"unknown atomic swap journal state: {state!r}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_artifact(artifact: Path, expected_sha256: str) -> str:
    artifact = Path(artifact)
    if not artifact.is_file():
        raise ValueError(f"release artifact does not exist: {artifact}")
    actual = _sha256_file(artifact)
    if actual.lower() != str(expected_sha256).strip().lower():
        raise ValueError(
            f"artifact sha256 mismatch: expected {expected_sha256}, got {actual}"
        )
    return actual


def verify_source_baseline(
    paths: SwapPaths,
    *,
    expected_pm_version: str,
) -> dict[str, str]:
    if paths.rollback.exists():
        raise RecoveryRequired(f"unexpected rollback directory exists: {paths.rollback.name}")
    if paths.candidate.exists():
        raise RecoveryRequired(f"unexpected candidate directory exists: {paths.candidate.name}")

    source_version = _read_version(paths.app)
    if source_version != paths.from_version:
        raise RecoveryRequired(
            f"source version mismatch: expected {paths.from_version}, got {source_version!r}"
        )

    pm_version_file = (
        paths.app
        / "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt"
    )
    source_pm_version = (
        pm_version_file.read_text(encoding="utf-8").strip()
        if pm_version_file.is_file()
        else None
    )
    if source_pm_version != expected_pm_version:
        raise RecoveryRequired(
            "source PM version mismatch: "
            f"expected {expected_pm_version}, got {source_pm_version!r}"
        )

    return {
        "source_version": source_version,
        "source_pm_version": source_pm_version,
    }


def verify_same_filesystem(
    paths: SwapPaths,
    *,
    device_ids: tuple[int, int, int] | None = None,
) -> dict[str, int]:
    if device_ids is None:
        if not paths.root.is_dir():
            raise RecoveryRequired(f"project root missing: {paths.root}")
        if not paths.app.is_dir():
            raise RecoveryRequired(f"active App missing: {paths.app}")
        if not paths.candidate.is_dir():
            raise RecoveryRequired(f"candidate missing: {paths.candidate}")
        root_dev = paths.root.stat().st_dev
        app_dev = paths.app.stat().st_dev
        candidate_dev = paths.candidate.stat().st_dev
    else:
        root_dev, app_dev, candidate_dev = device_ids

    if len({root_dev, app_dev, candidate_dev}) != 1:
        raise RecoveryRequired(
            "atomic App swap requires root, active App and candidate on the same filesystem"
        )

    return {
        "root_dev": int(root_dev),
        "app_dev": int(app_dev),
        "candidate_dev": int(candidate_dev),
    }


def probe_sibling_rename(paths: SwapPaths) -> dict[str, str]:
    """Prove same-parent rename rights without ever renaming active App."""
    root = paths.root
    if not root.is_dir():
        raise RecoveryRequired(f"project root missing: {root}")
    if not paths.app.is_dir():
        raise RecoveryRequired(f"active App missing: {paths.app}")

    old = Path(tempfile.mkdtemp(prefix=".atomic_swap_probe_old_", dir=str(root)))
    new = Path(tempfile.mkdtemp(prefix=".atomic_swap_probe_new_", dir=str(root)))
    rollback = root / f"{old.name}.rollback"
    active = root / f"{new.name}.active"
    old_marker = old / "identity.txt"
    new_marker = new / "identity.txt"
    old_marker.write_text("old\n", encoding="utf-8")
    new_marker.write_text("new\n", encoding="utf-8")

    try:
        old.rename(rollback)
        new.rename(active)
        if (rollback / "identity.txt").read_text(encoding="utf-8").strip() != "old":
            raise RecoveryRequired("sibling rename probe lost old identity")
        if (active / "identity.txt").read_text(encoding="utf-8").strip() != "new":
            raise RecoveryRequired("sibling rename probe lost new identity")
        active.rename(new)
        rollback.rename(old)
    finally:
        for directory in (old, new, rollback, active):
            marker = directory / "identity.txt"
            if marker.is_file():
                marker.unlink()
            if directory.is_dir():
                directory.rmdir()

    return {"status": "GREEN"}


_REQUIRED_RELEASE_FILES = {
    "README.md",
    "INSTALL.md",
    "CHANGELOG.md",
    "MANIFEST.sha256",
    "SHA256SUMS.json",
    "repository.yaml",
    "VERSIE.txt",
    "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt",
}
_FORBIDDEN_PARTS = {".pytest_cache", "__pycache__"}


def _member_path(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe ZIP member: {name}")
    return path


def _is_forbidden_release_path(path: Path) -> bool:
    return (
        any(part in _FORBIDDEN_PARTS for part in path.parts)
        or path.name == ".DS_Store"
        or path.suffix in {".pyc", ".pyo"}
    )


def _safe_zip_infos(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos: list[zipfile.ZipInfo] = []
    for info in zf.infolist():
        path = _member_path(info.filename)
        if _is_forbidden_release_path(path):
            raise ValueError(f"forbidden release member: {info.filename}")
        mode = (info.external_attr >> 16) & 0o170000
        if mode and stat.S_ISLNK(mode):
            raise ValueError(f"unsafe ZIP member symlink: {info.filename}")
        infos.append(info)
    return infos


def _read_pm_version(app_dir: Path) -> str | None:
    version_file = (
        app_dir / "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt"
    )
    if not version_file.is_file():
        return None
    return version_file.read_text(encoding="utf-8").strip()


def _verify_manifest(candidate: Path) -> int:
    manifest = candidate / "MANIFEST.sha256"
    if not manifest.is_file():
        raise RecoveryRequired("candidate manifest missing")

    checked = 0
    seen: set[str] = set()
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise RecoveryRequired(f"candidate manifest row invalid: {raw_line!r}")
        expected, rel = parts
        rel = rel.strip()
        if len(expected) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in expected):
            raise RecoveryRequired(f"candidate manifest sha invalid: {raw_line!r}")
        rel_path = _member_path(rel)
        if _is_forbidden_release_path(rel_path):
            raise RecoveryRequired(f"candidate manifest contains forbidden path: {rel}")
        rel_norm = rel_path.as_posix()
        if rel_norm in seen:
            raise RecoveryRequired(f"candidate manifest duplicate path: {rel_norm}")
        seen.add(rel_norm)
        target = candidate / rel_path
        if not target.is_file():
            raise RecoveryRequired(f"candidate manifest file missing: {rel_norm}")
        actual = _sha256_file(target)
        if actual.lower() != expected.lower():
            raise RecoveryRequired(
                f"candidate manifest mismatch: {rel_norm} expected {expected}, got {actual}"
            )
        checked += 1
    if checked == 0:
        raise RecoveryRequired("candidate manifest is empty")
    return checked


def verify_candidate(
    paths: SwapPaths,
    *,
    expected_pm_version: str,
) -> dict[str, Any]:
    candidate = paths.candidate
    if not candidate.is_dir():
        raise RecoveryRequired(f"candidate directory missing: {candidate}")

    for required in sorted(_REQUIRED_RELEASE_FILES):
        if not (candidate / required).is_file():
            raise RecoveryRequired(f"candidate required file missing: {required}")

    for item in candidate.rglob("*"):
        rel = item.relative_to(candidate)
        if _is_forbidden_release_path(rel):
            raise RecoveryRequired(f"candidate contains forbidden release member: {rel.as_posix()}")
        if item.is_symlink():
            raise RecoveryRequired(f"candidate contains symlink: {rel.as_posix()}")

    target_version = _read_version(candidate)
    if target_version != paths.to_version:
        raise RecoveryRequired(
            f"target version mismatch: expected {paths.to_version}, got {target_version!r}"
        )

    target_pm_version = _read_pm_version(candidate)
    if target_pm_version != expected_pm_version:
        raise RecoveryRequired(
            "target PM version mismatch: "
            f"expected {expected_pm_version}, got {target_pm_version!r}"
        )

    manifest_files = _verify_manifest(candidate)
    return {
        "target_version": target_version,
        "target_pm_version": target_pm_version,
        "manifest_files": manifest_files,
    }


def materialize_candidate(
    paths: SwapPaths,
    artifact: Path,
    *,
    expected_pm_version: str,
) -> dict[str, Any]:
    artifact = Path(artifact)
    if not artifact.is_file():
        raise ValueError(f"release artifact does not exist: {artifact}")
    if paths.candidate.exists():
        raise RecoveryRequired(f"candidate already exists: {paths.candidate.name}")
    if paths.rollback.exists():
        raise RecoveryRequired(f"rollback already exists: {paths.rollback.name}")

    with zipfile.ZipFile(artifact) as zf:
        infos = _safe_zip_infos(zf)
        bad = zf.testzip()
        if bad:
            raise RecoveryRequired(f"release ZIP integrity failed at member: {bad}")
        paths.candidate.mkdir()
        try:
            zf.extractall(paths.candidate, members=infos)
            return verify_candidate(paths, expected_pm_version=expected_pm_version)
        except Exception:
            shutil.rmtree(paths.candidate, ignore_errors=True)
            raise


def _event(event_hook, event: str) -> None:
    if event_hook is not None:
        event_hook(event)


def _verify_active_target(paths: SwapPaths, *, expected_pm_version: str) -> dict[str, Any]:
    active = paths.app
    if not active.is_dir():
        raise RecoveryRequired(f"active target directory missing: {active}")
    for required in sorted(_REQUIRED_RELEASE_FILES):
        if not (active / required).is_file():
            raise RecoveryRequired(f"active target required file missing: {required}")
    target_version = _read_version(active)
    if target_version != paths.to_version:
        raise RecoveryRequired(
            f"target version mismatch: expected {paths.to_version}, got {target_version!r}"
        )
    target_pm_version = _read_pm_version(active)
    if target_pm_version != expected_pm_version:
        raise RecoveryRequired(
            "target PM version mismatch: "
            f"expected {expected_pm_version}, got {target_pm_version!r}"
        )
    manifest_files = _verify_manifest(active)
    return {
        "target_version": target_version,
        "target_pm_version": target_pm_version,
        "manifest_files": manifest_files,
    }


def _failed_target_path(paths: SwapPaths) -> Path:
    index = 1
    while True:
        candidate = paths.root / f"App.__failed_{paths.to_version}_{index:03d}"
        if not candidate.exists():
            return candidate
        index += 1


def _write_rolled_back(paths: SwapPaths, *, artifact_sha256: str, error: str) -> dict[str, Any]:
    return write_journal_atomic(
        paths,
        state="ROLLED_BACK",
        artifact_sha256=artifact_sha256,
        error=error,
    )


def perform_swap(
    paths: SwapPaths,
    *,
    artifact_sha256: str,
    expected_target_pm_version: str,
    event_hook=None,
) -> dict[str, Any]:
    if paths.rollback.exists():
        raise RecoveryRequired(f"rollback already exists: {paths.rollback.name}")
    _require_version(paths.app, paths.from_version, label="source App")
    verify_candidate(paths, expected_pm_version=expected_target_pm_version)
    verify_same_filesystem(paths)

    phase = "PREPARED"
    write_journal_atomic(paths, state="PREPARED", artifact_sha256=artifact_sha256)
    _event(event_hook, "journal:PREPARED")

    try:
        paths.app.rename(paths.rollback)
        phase = "OLD_RENAMED_PHYSICAL"
        _event(event_hook, "rename:App->rollback")

        write_journal_atomic(paths, state="OLD_RENAMED", artifact_sha256=artifact_sha256)
        phase = "OLD_RENAMED"
        _event(event_hook, "journal:OLD_RENAMED")

        paths.candidate.rename(paths.app)
        phase = "NEW_ACTIVE_PHYSICAL"
        _event(event_hook, "rename:candidate->App")

        write_journal_atomic(paths, state="NEW_ACTIVE", artifact_sha256=artifact_sha256)
        phase = "NEW_ACTIVE"
        _event(event_hook, "journal:NEW_ACTIVE")

        _verify_active_target(paths, expected_pm_version=expected_target_pm_version)
        _event(event_hook, "validate:active-target")

        result = write_journal_atomic(
            paths,
            state="LIVE_ACCEPTANCE",
            artifact_sha256=artifact_sha256,
        )
        phase = "LIVE_ACCEPTANCE"
        _event(event_hook, "journal:LIVE_ACCEPTANCE")
        return result
    except Exception as exc:
        if phase in {"OLD_RENAMED_PHYSICAL", "OLD_RENAMED"}:
            if not paths.app.exists() and paths.rollback.is_dir():
                paths.rollback.rename(paths.app)
                _write_rolled_back(
                    paths,
                    artifact_sha256=artifact_sha256,
                    error=f"swap failed before candidate activation: {exc}",
                )
            else:
                raise RecoveryRequired(
                    "automatic rollback after first rename could not prove a safe restore state"
                ) from exc
        elif phase in {"NEW_ACTIVE_PHYSICAL", "NEW_ACTIVE", "LIVE_ACCEPTANCE"}:
            failed = _failed_target_path(paths)
            if not paths.app.is_dir() or not paths.rollback.is_dir():
                raise RecoveryRequired(
                    "automatic rollback after activation could not prove active/rollback directories"
                ) from exc
            paths.app.rename(failed)
            try:
                paths.rollback.rename(paths.app)
            except Exception as rollback_exc:
                raise RecoveryRequired(
                    f"target quarantined as {failed.name} but source restore failed"
                ) from rollback_exc
            _write_rolled_back(
                paths,
                artifact_sha256=artifact_sha256,
                error=f"swap failed after candidate activation: {exc}",
            )
        raise


def finalize_acceptance(
    paths: SwapPaths,
    *,
    expected_target_pm_version: str,
) -> dict[str, Any]:
    journal = load_journal(paths)
    if journal is None:
        raise RecoveryRequired("cannot finalize acceptance without atomic swap journal")
    if str(journal.get("state", "")) != "LIVE_ACCEPTANCE":
        raise RecoveryRequired(
            "finalize_acceptance requires journal state LIVE_ACCEPTANCE"
        )
    if str(journal.get("from_version", "")) != paths.from_version:
        raise RecoveryRequired("journal source version mismatch during acceptance")
    if str(journal.get("to_version", "")) != paths.to_version:
        raise RecoveryRequired("journal target version mismatch during acceptance")

    _verify_active_target(paths, expected_pm_version=expected_target_pm_version)
    _require_version(paths.rollback, paths.from_version, label="rollback App")

    return write_journal_atomic(
        paths,
        state="ACCEPTED",
        artifact_sha256=str(journal.get("artifact_sha256", "")),
    )


def rollback_after_activation_failure(
    paths: SwapPaths,
    *,
    reason: str,
) -> dict[str, Any]:
    journal = load_journal(paths)
    if journal is None:
        raise RecoveryRequired("cannot rollback without atomic swap journal")
    state = str(journal.get("state", ""))
    if state not in {"NEW_ACTIVE", "LIVE_ACCEPTANCE"}:
        raise RecoveryRequired(
            "explicit activation rollback requires NEW_ACTIVE or LIVE_ACCEPTANCE"
        )
    if not paths.app.is_dir():
        raise RecoveryRequired("explicit activation rollback requires active App")
    if not paths.rollback.is_dir():
        raise RecoveryRequired("explicit activation rollback requires rollback App")

    _require_version(paths.rollback, paths.from_version, label="rollback App")
    failed = _failed_target_path(paths)
    paths.app.rename(failed)
    try:
        paths.rollback.rename(paths.app)
    except Exception as exc:
        raise RecoveryRequired(
            f"target quarantined as {failed.name} but explicit source restore failed"
        ) from exc

    _require_version(paths.app, paths.from_version, label="restored App")
    return _write_rolled_back(
        paths,
        artifact_sha256=str(journal.get("artifact_sha256", "")),
        error=f"explicit rollback after activation failure: {reason}",
    )


def assert_no_release_conflict(
    root: Path,
    *,
    current_artifact: Path | None = None,
) -> None:
    """Fail closed on competing release work; optionally allow one owned installer artifact."""
    root = Path(root)
    inbox = root / "Inbox"
    installer_context = current_artifact is not None
    artifact = Path(current_artifact).resolve() if current_artifact is not None else None

    installer_lock = inbox / ".installer.lock"
    if installer_context:
        if not installer_lock.is_dir():
            raise RecoveryRequired("installer context requires active installer lock")
    elif installer_lock.exists():
        raise RecoveryRequired(f"installer conflict is active: {installer_lock}")

    processing = inbox / "processing"
    processing_zips = sorted(p.resolve() for p in processing.glob("*.zip")) if processing.is_dir() else []
    if installer_context:
        if artifact is None or not processing.is_dir() or artifact.parent != processing.resolve():
            raise RecoveryRequired("installer context artifact must be the processing release ZIP")
        if processing_zips != [artifact]:
            raise RecoveryRequired("processing release conflict is active beyond owned installer artifact")
    elif processing_zips:
        raise RecoveryRequired("processing release conflict is active")

    incoming = inbox / "incoming"
    if incoming.is_dir() and any(incoming.glob("*.zip")):
        raise RecoveryRequired("incoming release conflict is active")

    atomic_lock = inbox / ".atomic_app_swap.lock"
    if atomic_lock.exists():
        raise RecoveryRequired(f"atomic swap lock conflict is active: {atomic_lock}")


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _cli_prepare_and_swap(args) -> dict[str, Any]:
    root = Path(args.root)
    artifact = Path(args.artifact)
    if args.installer_context:
        assert_no_release_conflict(root, current_artifact=artifact)
    else:
        assert_no_release_conflict(root)
    paths = SwapPaths.for_release(root, args.from_version, args.to_version)
    acquire_swap_lock(paths)
    try:
        artifact_sha256 = verify_release_artifact(Path(args.artifact), args.expected_sha256)
        verify_source_baseline(paths, expected_pm_version=args.from_pm_version)
        materialize_candidate(
            paths,
            Path(args.artifact),
            expected_pm_version=args.to_pm_version,
        )
        verify_same_filesystem(paths)
        probe_sibling_rename(paths)
        return perform_swap(
            paths,
            artifact_sha256=artifact_sha256,
            expected_target_pm_version=args.to_pm_version,
        )
    finally:
        release_swap_lock(paths)


def _cli_rollback(args) -> dict[str, Any]:
    paths = SwapPaths.for_release(Path(args.root), args.from_version, args.to_version)
    acquire_swap_lock(paths)
    try:
        return rollback_after_activation_failure(paths, reason=args.reason)
    finally:
        release_swap_lock(paths)


def _cli_accept(args) -> dict[str, Any]:
    paths = SwapPaths.for_release(Path(args.root), args.from_version, args.to_version)
    acquire_swap_lock(paths)
    try:
        return finalize_acceptance(
            paths,
            expected_target_pm_version=args.to_pm_version,
        )
    finally:
        release_swap_lock(paths)


def _cli_status(args) -> dict[str, Any]:
    root = Path(args.root)
    journal = root / "Inbox/atomic_app_swap_state.json"
    if not journal.is_file():
        return {"state": "NONE"}
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RecoveryRequired("atomic swap journal is not an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Atomic QNAP App sibling-directory swap")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare-and-swap")
    prepare.add_argument("--root", required=True)
    prepare.add_argument("--artifact", required=True)
    prepare.add_argument("--expected-sha256", required=True)
    prepare.add_argument("--from-version", required=True)
    prepare.add_argument("--from-pm-version", required=True)
    prepare.add_argument("--to-version", required=True)
    prepare.add_argument("--to-pm-version", required=True)
    prepare.add_argument("--installer-context", action="store_true")

    rollback = sub.add_parser("rollback")
    rollback.add_argument("--root", required=True)
    rollback.add_argument("--from-version", required=True)
    rollback.add_argument("--to-version", required=True)
    rollback.add_argument("--reason", required=True)

    accept = sub.add_parser("accept")
    accept.add_argument("--root", required=True)
    accept.add_argument("--from-version", required=True)
    accept.add_argument("--to-version", required=True)
    accept.add_argument("--to-pm-version", required=True)

    status = sub.add_parser("status")
    status.add_argument("--root", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-and-swap":
            payload = _cli_prepare_and_swap(args)
        elif args.command == "rollback":
            payload = _cli_rollback(args)
        elif args.command == "accept":
            payload = _cli_accept(args)
        elif args.command == "status":
            payload = _cli_status(args)
        else:
            raise RecoveryRequired(f"unknown command: {args.command}")
    except Exception as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return 2

    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

