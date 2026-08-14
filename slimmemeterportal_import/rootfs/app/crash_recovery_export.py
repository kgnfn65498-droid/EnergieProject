#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import hashlib
from pathlib import Path, PurePosixPath
import zipfile

REQUIRED_PROJECT_ROOTS = ("App", "Data", "Backups", "Inbox", "Infra")
EXCLUDED_BASENAME_PATTERNS = (
    "Energie_Complete_Backup_*.zip",
    "FULL_RECOVERY*.tar.gz",
)
SNAPSHOT_RUNTIME_PATHS = frozenset({
    PurePosixPath("Data/01_Input/_scheduler/quarter_hour_heartbeat.json"),
})


@dataclass(frozen=True)
class ProjectFile:
    relative_path: Path
    size: int
    mtime_ns: int
    snapshot_bytes: bytes | None = None


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


def _snapshot_runtime_file(path: Path, relative: Path) -> ProjectFile:
    """Capture one stable version of an explicitly approved changing runtime file."""
    for _attempt in range(2):
        try:
            before = path.stat()
            data = path.read_bytes()
            after = path.stat()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Projectinhoud wijzigde tijdens Crash Recovery snapshot: "
                f"{relative} verdween."
            ) from exc
        if (
            before.st_size == after.st_size == len(data)
            and before.st_mtime_ns == after.st_mtime_ns
        ):
            return ProjectFile(
                relative_path=relative,
                size=len(data),
                mtime_ns=after.st_mtime_ns,
                snapshot_bytes=data,
            )
    raise RuntimeError(
        "Projectinhoud bleef wijzigen tijdens Crash Recovery snapshot: "
        f"{relative}."
    )


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
        relative_posix = PurePosixPath(relative.as_posix())
        if relative_posix in SNAPSHOT_RUNTIME_PATHS:
            files.append(_snapshot_runtime_file(path, relative))
            continue
        stat = path.stat()
        files.append(
            ProjectFile(
                relative_path=relative,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return files


def build_recovery_export(project_root: Path, output_zip: Path) -> ExportBuildResult:
    """Build one restorable ZIP whose only top-level directory is EnergieProject/."""
    project_root = project_root.resolve()
    output_zip = output_zip.resolve()
    _require_project_roots(project_root)

    if output_zip == project_root or project_root in output_zip.parents:
        raise RuntimeError("Crash Recovery export-ZIP mag niet binnen EnergieProject staan.")

    inventory = collect_project_files(project_root)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    try:
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
                arcname = PurePosixPath("EnergieProject") / PurePosixPath(
                    item.relative_path.as_posix()
                )
                if item.snapshot_bytes is not None:
                    archive.writestr(arcname.as_posix(), item.snapshot_bytes)
                else:
                    archive.write(source, arcname.as_posix())

        for item in inventory:
            if item.snapshot_bytes is not None:
                continue
            source = project_root / item.relative_path
            try:
                stat = source.stat()
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "Projectinhoud wijzigde tijdens Crash Recovery export: "
                    f"{item.relative_path} verdween."
                ) from exc
            if stat.st_size != item.size or stat.st_mtime_ns != item.mtime_ns:
                raise RuntimeError(
                    "Projectinhoud wijzigde tijdens Crash Recovery export: "
                    f"{item.relative_path}."
                )

        total_bytes = sum(item.size for item in inventory)
        return ExportBuildResult(
            zip_path=output_zip,
            file_count=len(inventory),
            total_bytes=total_bytes,
            sha256=sha256_file(output_zip),
        )
    except Exception:
        try:
            output_zip.unlink(missing_ok=True)
        except OSError:
            pass
        raise


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
