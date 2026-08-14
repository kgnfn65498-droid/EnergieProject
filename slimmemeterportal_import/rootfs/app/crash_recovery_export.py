#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import errno
import fnmatch
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

REQUIRED_PROJECT_ROOTS = ("App", "Data", "Backups", "Inbox", "Infra")
EXCLUDED_BASENAME_PATTERNS = (
    "Energie_Complete_Backup_*.zip",
    "FULL_RECOVERY*.tar.gz",
)


@dataclass(frozen=True)
class ProjectFile:
    relative_path: Path
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class ExportBuildResult:
    zip_path: Path
    file_count: int
    total_bytes: int
    sha256: str


@dataclass(frozen=True)
class ExportVerifyResult:
    valid: bool
    file_count: int
    sha256: str
    top_level_ok: bool
    required_roots_ok: bool
    excluded_hits: tuple[str, ...]
    error: str = ""


def should_include_project_file(relative_path: Path) -> bool:
    """Return True for project content except the explicitly approved exclusions."""
    name = relative_path.name
    if name == ".DS_Store":
        return False
    return not any(
        fnmatch.fnmatchcase(name, pattern)
        for pattern in EXCLUDED_BASENAME_PATTERNS
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _require_project_roots(project_root: Path) -> None:
    missing = [
        name
        for name in REQUIRED_PROJECT_ROOTS
        if not (project_root / name).is_dir()
    ]
    if missing:
        raise RuntimeError(
            "EnergieProject hoofdmappen ontbreken: " + ", ".join(missing)
        )


class _SnapshotChanged(RuntimeError):
    pass


def _snapshot_file_to_temp(
    source: Path,
    *,
    temp_dir: Path,
    relative: Path,
    attempts: int = 3,
) -> tuple[Path, int]:
    """Capture one internally stable file image without requiring the live path to stay frozen afterwards."""
    last_reason = "onbekende wijziging"
    for _attempt in range(max(1, attempts)):
        tmp_handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".crash-recovery-snapshot-",
            dir=temp_dir,
            delete=False,
        )
        tmp_path = Path(tmp_handle.name)
        keep_snapshot = False
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(source, flags)
            except FileNotFoundError:
                last_reason = f"{relative} verdween voor de snapshot"
                continue
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise RuntimeError(
                        f"Symlink in EnergieProject kan niet worden opgenomen: {relative}"
                    ) from exc
                raise

            total = 0
            with os.fdopen(fd, "rb") as src, tmp_handle:
                before = os.fstat(src.fileno())
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp_handle.write(chunk)
                    total += len(chunk)
                tmp_handle.flush()
                after = os.fstat(src.fileno())

            if (
                before.st_size == after.st_size == total
                and before.st_mtime_ns == after.st_mtime_ns
            ):
                keep_snapshot = True
                return tmp_path, total

            last_reason = f"{relative} wijzigde tijdens het lezen"
        finally:
            try:
                tmp_handle.close()
            except Exception:
                pass
            if not keep_snapshot:
                tmp_path.unlink(missing_ok=True)

    raise _SnapshotChanged(last_reason)


def collect_project_files(project_root: Path) -> list[ProjectFile]:
    project_root = project_root.resolve()
    _require_project_roots(project_root)

    files: list[ProjectFile] = []
    for path in sorted(project_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RuntimeError(
                f"Symlink in EnergieProject kan niet stil worden overgeslagen: {path}"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if not should_include_project_file(relative):
            continue
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise _SnapshotChanged(f"{relative} verdween tijdens inventarisatie") from exc
        files.append(
            ProjectFile(
                relative_path=relative,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return files


def _build_recovery_export_once(
    project_root: Path,
    output_zip: Path,
) -> ExportBuildResult:
    inventory = collect_project_files(project_root)
    initial_paths = tuple(item.relative_path.as_posix() for item in inventory)
    total_bytes = 0

    with zipfile.ZipFile(
        output_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as archive:
        for root_name in REQUIRED_PROJECT_ROOTS:
            archive.writestr(f"EnergieProject/{root_name}/", b"")

        for item in inventory:
            source = project_root / item.relative_path
            arcname = (
                PurePosixPath("EnergieProject")
                / PurePosixPath(item.relative_path.as_posix())
            ).as_posix()
            snapshot_path = None
            try:
                snapshot_path, snapshot_size = _snapshot_file_to_temp(
                    source,
                    temp_dir=output_zip.parent,
                    relative=item.relative_path,
                )
                archive.write(snapshot_path, arcname)
                total_bytes += snapshot_size
            finally:
                if snapshot_path is not None:
                    snapshot_path.unlink(missing_ok=True)

    final_inventory = collect_project_files(project_root)
    final_paths = tuple(item.relative_path.as_posix() for item in final_inventory)
    if final_paths != initial_paths:
        raise _SnapshotChanged(
            "de projectbestandsset wijzigde tijdens de Crash Recovery snapshot"
        )

    return ExportBuildResult(
        zip_path=output_zip,
        file_count=len(inventory),
        total_bytes=total_bytes,
        sha256=sha256_file(output_zip),
    )


def build_recovery_export(project_root: Path, output_zip: Path) -> ExportBuildResult:
    """Build a restorable live-project snapshot under one EnergieProject/ top level.

    Each file is copied to a short-lived stable snapshot first. Normal 24/7 runtime
    writers may replace a path after that snapshot without invalidating the export.
    A file that changes while it is actually being read, or a changing path set,
    causes the whole ZIP build to retry instead of silently accepting a torn file.
    """
    project_root = project_root.resolve()
    output_zip = output_zip.resolve()
    _require_project_roots(project_root)

    if output_zip == project_root or project_root in output_zip.parents:
        raise RuntimeError("Crash Recovery export-ZIP mag niet binnen EnergieProject staan.")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    last_change = ""
    for attempt in range(3):
        output_zip.unlink(missing_ok=True)
        try:
            return _build_recovery_export_once(project_root, output_zip)
        except _SnapshotChanged as exc:
            last_change = str(exc)
            output_zip.unlink(missing_ok=True)
            if attempt < 2:
                continue
            raise RuntimeError(
                "Projectinhoud bleef wijzigen tijdens Crash Recovery snapshot: "
                + last_change
            ) from exc
        except Exception:
            output_zip.unlink(missing_ok=True)
            raise

    raise RuntimeError(
        "Crash Recovery snapshot kon niet worden opgebouwd."
    )


def verify_recovery_export(zip_path: Path) -> ExportVerifyResult:
    zip_path = zip_path.resolve()
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            bad_member = archive.testzip()
            infos = archive.infolist()
            file_infos = [info for info in infos if not info.is_dir()]
            names = [info.filename for info in infos]
            file_names = [info.filename for info in file_infos]

            top_level_ok = bool(names) and all(
                name.startswith("EnergieProject/")
                for name in names
            )
            required_roots_ok = all(
                any(
                    name == f"EnergieProject/{root_name}/"
                    or name.startswith(f"EnergieProject/{root_name}/")
                    for name in names
                )
                for root_name in REQUIRED_PROJECT_ROOTS
            )

            excluded_hits: list[str] = []
            for name in file_names:
                basename = PurePosixPath(name).name
                if basename == ".DS_Store" or any(
                    fnmatch.fnmatchcase(basename, pattern)
                    for pattern in EXCLUDED_BASENAME_PATTERNS
                ):
                    excluded_hits.append(name)

            sha = sha256_file(zip_path)
            valid = (
                bad_member is None
                and top_level_ok
                and required_roots_ok
                and not excluded_hits
            )
            error = ""
            if bad_member is not None:
                error = f"ZIP-integriteit fout bij {bad_member}"
            elif not top_level_ok:
                error = "ZIP bevat inhoud buiten EnergieProject/."
            elif not required_roots_ok:
                error = "Niet alle vijf EnergieProject-hoofdmappen zijn aanwezig."
            elif excluded_hits:
                error = "Expliciet uitgesloten backup-in-backup-bestanden aangetroffen."

            return ExportVerifyResult(
                valid=valid,
                file_count=len(file_infos),
                sha256=sha,
                top_level_ok=top_level_ok,
                required_roots_ok=required_roots_ok,
                excluded_hits=tuple(excluded_hits),
                error=error,
            )
    except (OSError, zipfile.BadZipFile) as exc:
        return ExportVerifyResult(
            valid=False,
            file_count=0,
            sha256="",
            top_level_ok=False,
            required_roots_ok=False,
            excluded_hits=(),
            error=f"{type(exc).__name__}: {exc}",
        )
