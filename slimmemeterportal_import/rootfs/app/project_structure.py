from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

STRUCTURE_VERSION = "32.2.1"
REPORTS_RELATIVE = Path("Data/02_Output/Rapportages")
KNOWLEDGE_BASE_RELATIVE = REPORTS_RELATIVE / "KnowledgeBase"
HISTORY_RELATIVE = REPORTS_RELATIVE / "Verbruikshistorie"
HISTORY_MASTER_RELATIVE = HISTORY_RELATIVE / "Energie_verbruik_historie.xlsx"
HISTORY_ARCHIVE_RELATIVE = HISTORY_RELATIVE / "Archief"
HISTORICAL_DATA_INDEX_RELATIVE = HISTORY_RELATIVE / "Historische_data_index.md"
HISTORICAL_DESIGN_RELATIVE = HISTORY_RELATIVE / "Energie_verbruik_historie_design.md"
HISTORICAL_BOOTSTRAP_STATUS_RELATIVE = HISTORY_RELATIVE / "Energie_verbruik_historie_bootstrap_status.json"
STRUCTURE_STATUS_RELATIVE = KNOWLEDGE_BASE_RELATIVE / "Structuurmigratie_v32.2_status.json"
STRUCTURE_BACKUP_RELATIVE = Path("Backups/StructureMigration_v32.2/pre_migration")
KNOWLEDGE_BASE_REHOME_RELATIVE = REPORTS_RELATIVE / ".KnowledgeBase_v32.2_rehome"

LEGACY_MASTER_RELATIVE = REPORTS_RELATIVE / "Energie_verbruik_historie.xlsx"
LEGACY_ARCHIVE_RELATIVE = REPORTS_RELATIVE / "Archief"
LEGACY_HISTORICAL_DATA_INDEX_RELATIVE = REPORTS_RELATIVE / "Historische_data_index.md"
LEGACY_HISTORICAL_DESIGN_RELATIVE = REPORTS_RELATIVE / "Energie_verbruik_historie_design.md"
LEGACY_BOOTSTRAP_STATUS_RELATIVE = REPORTS_RELATIVE / "Energie_verbruik_historie_bootstrap_status.json"
LEGACY_ROADMAP_RELATIVE = REPORTS_RELATIVE / "EnergieProject_Roadmap.md"
LEGACY_APPARATUUR_INDEX_RELATIVE = REPORTS_RELATIVE / "Apparatuur_index.md"
LEGACY_MOBILE_SOCKET_LOG_RELATIVE = REPORTS_RELATIVE / "Mobiele_socket_meetlog.md"

ROADMAP_RELATIVE = KNOWLEDGE_BASE_RELATIVE / "EnergieProject_Roadmap.md"
APPARATUUR_INDEX_RELATIVE = KNOWLEDGE_BASE_RELATIVE / "Apparatuur_index.md"
MOBILE_SOCKET_LOG_RELATIVE = KNOWLEDGE_BASE_RELATIVE / "Mobiele_socket_meetlog.md"

FILE_MOVES = (
    (LEGACY_MASTER_RELATIVE, HISTORY_MASTER_RELATIVE),
    (LEGACY_HISTORICAL_DATA_INDEX_RELATIVE, HISTORICAL_DATA_INDEX_RELATIVE),
    (LEGACY_HISTORICAL_DESIGN_RELATIVE, HISTORICAL_DESIGN_RELATIVE),
    (LEGACY_BOOTSTRAP_STATUS_RELATIVE, HISTORICAL_BOOTSTRAP_STATUS_RELATIVE),
    (LEGACY_ROADMAP_RELATIVE, ROADMAP_RELATIVE),
    (LEGACY_APPARATUUR_INDEX_RELATIVE, APPARATUUR_INDEX_RELATIVE),
    (LEGACY_MOBILE_SOCKET_LOG_RELATIVE, MOBILE_SOCKET_LOG_RELATIVE),
)

def _active_doc_relatives(project_root: Path) -> list[Path]:
    kb_root = project_root / KNOWLEDGE_BASE_RELATIVE
    docs: set[Path] = set()
    if kb_root.is_dir():
        docs.update(path.relative_to(project_root) for path in kb_root.glob("*.md") if path.is_file())
    roadmap = project_root / ROADMAP_RELATIVE
    if roadmap.is_file():
        docs.add(ROADMAP_RELATIVE)
    return sorted(docs, key=lambda p: p.as_posix())


PATH_REPLACEMENTS = (
    ("Data/02_Output/Rapportages/EnergieProject_Roadmap.md", "Data/02_Output/Rapportages/KnowledgeBase/EnergieProject_Roadmap.md"),
    ("Data/02_Output/Rapportages/Energie_verbruik_historie.xlsx", "Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx"),
    ("Data/02_Output/Rapportages/Energie_verbruik_historie_bootstrap_status.json", "Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_bootstrap_status.json"),
    ("Data/02_Output/Rapportages/Historische_data_index.md", "Data/02_Output/Rapportages/Verbruikshistorie/Historische_data_index.md"),
    ("Data/02_Output/Rapportages/Energie_verbruik_historie_design.md", "Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_design.md"),
    ("Data/02_Output/Rapportages/Archief/", "Data/02_Output/Rapportages/Verbruikshistorie/Archief/"),
    ("Data/02_Output/Rapportages/Apparatuur_index.md", "Data/02_Output/Rapportages/KnowledgeBase/Apparatuur_index.md"),
    ("Data/02_Output/Rapportages/Mobiele_socket_meetlog.md", "Data/02_Output/Rapportages/KnowledgeBase/Mobiele_socket_meetlog.md"),
    ("EnergieProject/KnowledgeBase/", "Data/02_Output/Rapportages/KnowledgeBase/"),
    ("EnergieProject/Verbruikshistorie/", "Data/02_Output/Rapportages/Verbruikshistorie/"),
    ("EnergieProject/Roadmap.md", "Data/02_Output/Rapportages/KnowledgeBase/EnergieProject_Roadmap.md"),
    ("`Historische_data_index.md`", "`Data/02_Output/Rapportages/Verbruikshistorie/Historische_data_index.md`"),
    ("`Energie_verbruik_historie.xlsx`", "`Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx`"),
    ("`Energie_verbruik_historie_bootstrap_status.json`", "`Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_bootstrap_status.json`"),
    ("`Energie_verbruik_historie_design.md`", "`Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_design.md`"),
    ("`Archief/`", "`Data/02_Output/Rapportages/Verbruikshistorie/Archief/`"),
    ("Gebruik voor open werk de actuele `EnergieProject_Roadmap.md` buiten deze map.", "Gebruik voor open werk de actuele `EnergieProject_Roadmap.md` in deze KnowledgeBase-map."),
    ("Raadpleeg de actuele roadmap buiten deze map voor open acties en prioriteiten.", "Raadpleeg `EnergieProject_Roadmap.md` in deze map voor open acties en prioriteiten."),
)

LOCATION_MARKER = "<!-- V32.2 LOCATION CONTRACT -->"

class StructureMigrationConflict(RuntimeError):
    pass



def _directory_accepts_atomic_write(directory: Path) -> bool:
    """Return True only when this runtime can create and atomically publish a file."""
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / f".v3221-write-probe.{os.getpid()}.tmp"
    published = directory / f".v3221-write-probe.{os.getpid()}.ok"
    try:
        probe.write_text("probe\n", encoding="utf-8")
        os.replace(probe, published)
        published.unlink()
        return True
    except OSError:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            published.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _tree_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StructureMigrationConflict(f"Symlink niet toegestaan in KnowledgeBase-rehome: {path}")
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = _sha256(path)
    return hashes


def _copy_tree_verified(source: Path, target: Path) -> None:
    source_hashes = _tree_file_hashes(source)
    target.mkdir(parents=True, exist_ok=True)
    for relative, expected in source_hashes.items():
        src = source / relative
        dst = target / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if _sha256(dst) != expected:
            raise StructureMigrationConflict(f"KnowledgeBase-rehome hash wijkt af: {relative}")
    if _tree_file_hashes(target) != source_hashes:
        raise StructureMigrationConflict("KnowledgeBase-rehome boom wijkt af na kopie")


def _ensure_writable_knowledge_base(project_root: Path) -> bool:
    """Rehome a pre-existing KB directory when HA cannot atomically write in it.

    QNAP report tooling can create a directory with ownership/ACL different from
    the Home Assistant add-on. Renaming from the writable parent preserves the
    original byte-for-byte while a new runtime-owned directory is created.
    """
    kb = project_root / KNOWLEDGE_BASE_RELATIVE
    rehome = project_root / KNOWLEDGE_BASE_REHOME_RELATIVE

    if not kb.exists():
        if rehome.exists():
            kb.mkdir(parents=True, exist_ok=True)
            _copy_tree_verified(rehome, kb)
            if not _directory_accepts_atomic_write(kb):
                raise StructureMigrationConflict("Nieuwe KnowledgeBase-map blijft niet schrijfbaar")
            return True
        kb.mkdir(parents=True, exist_ok=True)
        if not _directory_accepts_atomic_write(kb):
            raise StructureMigrationConflict("Nieuwe KnowledgeBase-map is niet schrijfbaar")
        return False

    if not kb.is_dir() or kb.is_symlink():
        raise StructureMigrationConflict(f"KnowledgeBase is geen gewone map: {KNOWLEDGE_BASE_RELATIVE}")

    if _directory_accepts_atomic_write(kb):
        if rehome.exists():
            original_paths = set(_tree_file_hashes(rehome))
            current_paths = set(_tree_file_hashes(kb))
            missing = sorted(original_paths - current_paths)
            if missing:
                raise StructureMigrationConflict(f"Achtergebleven KnowledgeBase-rehome mist actief bestand: {missing[0]}")
            return True
        return False

    if rehome.exists():
        raise StructureMigrationConflict("KnowledgeBase is niet schrijfbaar en rehome-backup bestaat al")

    kb.rename(rehome)
    kb.mkdir(parents=True, exist_ok=True)
    try:
        _copy_tree_verified(rehome, kb)
        if not _directory_accepts_atomic_write(kb):
            raise StructureMigrationConflict("Gerehomede KnowledgeBase-map is niet schrijfbaar")
    except Exception:
        # Laat de originele rehome-map altijd staan voor herstelbewijs.
        raise
    return True


def _finish_knowledge_base_rehome(project_root: Path, rehomed: bool) -> None:
    if not rehomed:
        return
    rehome = project_root / KNOWLEDGE_BASE_REHOME_RELATIVE
    kb = project_root / KNOWLEDGE_BASE_RELATIVE
    if rehome.is_dir():
        original_paths = set(_tree_file_hashes(rehome))
        current_paths = set(_tree_file_hashes(kb))
        missing = sorted(original_paths - current_paths)
        if missing:
            raise StructureMigrationConflict(f"Rehome-opruiming geblokkeerd; bestand ontbreekt: {missing[0]}")
        # De pre-migratiebackup bevat de originele hashes. Na succesvolle
        # document-rewrite mogen actieve Markdownbestanden bewust verschillen.
        shutil.rmtree(rehome)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_file_content(a: Path, b: Path) -> bool:
    if not a.is_file() or not b.is_file():
        return False
    if a.stat().st_size != b.stat().st_size:
        return False
    return _sha256(a) == _sha256(b)


def _assert_regular_file_or_absent(path: Path) -> None:
    if path.is_symlink():
        raise StructureMigrationConflict(f"Symlink niet toegestaan in structuurmigratie: {path}")
    if path.exists() and not path.is_file():
        raise StructureMigrationConflict(f"Verwacht bestand maar vond ander type: {path}")


def _preflight_pair(project_root: Path, source_rel: Path, target_rel: Path) -> None:
    source = project_root / source_rel
    target = project_root / target_rel
    _assert_regular_file_or_absent(source)
    _assert_regular_file_or_absent(target)
    if source.is_file() and target.is_file() and not _same_file_content(source, target):
        raise StructureMigrationConflict(
            f"Bron en doel verschillen; niets overschreven: {source_rel} -> {target_rel}"
        )


def _archive_pairs(project_root: Path) -> list[tuple[Path, Path]]:
    legacy_root = project_root / LEGACY_ARCHIVE_RELATIVE
    if legacy_root.is_symlink():
        raise StructureMigrationConflict(f"Symlink niet toegestaan: {LEGACY_ARCHIVE_RELATIVE}")
    if legacy_root.exists() and not legacy_root.is_dir():
        raise StructureMigrationConflict(f"Legacy Archief is geen map: {LEGACY_ARCHIVE_RELATIVE}")
    if not legacy_root.is_dir():
        return []
    pairs: list[tuple[Path, Path]] = []
    for source in sorted(legacy_root.glob("Energie_verbruik_historie_*.xlsx")):
        if source.is_symlink() or not source.is_file():
            raise StructureMigrationConflict(f"Ongeldig archiefitem: {source}")
        pairs.append((source.relative_to(project_root), HISTORY_ARCHIVE_RELATIVE / source.name))
    return pairs


def _backup_candidates(project_root: Path, archive_pairs: list[tuple[Path, Path]]) -> list[Path]:
    candidates: list[Path] = []
    for source_rel, _ in FILE_MOVES:
        if (project_root / source_rel).is_file():
            candidates.append(source_rel)
    for source_rel, _ in archive_pairs:
        if (project_root / source_rel).is_file():
            candidates.append(source_rel)
    for doc_rel in _active_doc_relatives(project_root):
        if (project_root / doc_rel).is_file():
            candidates.append(doc_rel)
    return sorted(set(candidates), key=lambda p: p.as_posix())


def _create_or_verify_backup(project_root: Path, candidates: list[Path]) -> dict[str, Any]:
    backup_root = project_root / STRUCTURE_BACKUP_RELATIVE
    manifest_path = backup_root / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("files") or []:
            relative = Path(item["path"])
            backup_file = backup_root / relative
            if not backup_file.is_file() or _sha256(backup_file) != item["sha256"]:
                raise StructureMigrationConflict(f"Bestaande structuurbackup ongeldig: {relative}")
        return manifest

    backup_root.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for relative in candidates:
        source = project_root / relative
        if not source.is_file():
            continue
        destination = backup_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        source_sha = _sha256(source)
        if _sha256(destination) != source_sha:
            raise StructureMigrationConflict(f"Backup-hash wijkt af: {relative}")
        files.append({"path": relative.as_posix(), "sha256": source_sha, "size": source.stat().st_size})
    manifest = {
        "version": STRUCTURE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    temp = manifest_path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, manifest_path)
    return manifest


def _copy_verify_remove(project_root: Path, source_rel: Path, target_rel: Path) -> dict[str, Any]:
    source = project_root / source_rel
    target = project_root / target_rel
    _assert_regular_file_or_absent(source)
    _assert_regular_file_or_absent(target)
    if not source.is_file():
        return {"source": source_rel.as_posix(), "target": target_rel.as_posix(), "action": "source_absent"}
    source_sha = _sha256(source)
    if target.is_file():
        if _sha256(target) != source_sha:
            raise StructureMigrationConflict(f"Doel bestaat met andere inhoud: {target_rel}")
        source.unlink()
        return {"source": source_rel.as_posix(), "target": target_rel.as_posix(), "action": "deduplicated", "sha256": source_sha}

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.v3220.{os.getpid()}.tmp")
    temp.unlink(missing_ok=True)
    shutil.copyfile(source, temp)
    if _sha256(temp) != source_sha:
        temp.unlink(missing_ok=True)
        raise StructureMigrationConflict(f"Tijdelijke kopie wijkt af: {source_rel}")
    os.replace(temp, target)
    if _sha256(target) != source_sha:
        raise StructureMigrationConflict(f"Doelhash wijkt af na publicatie: {target_rel}")
    source.unlink()
    return {"source": source_rel.as_posix(), "target": target_rel.as_posix(), "action": "moved", "sha256": source_sha}


def _rewrite_active_docs(project_root: Path) -> list[str]:
    changed: list[str] = []
    location_block = (
        "\n\n" + LOCATION_MARKER + "\n"
        "## Actueel locatiecontract v32.2.1\n\n"
        "Vanaf v32.2.1 zijn de canonieke actieve locaties:\n"
        "- Knowledge Base + Roadmap + apparatuur-/socketindex: `Data/02_Output/Rapportages/KnowledgeBase/`.\n"
        "- Historische energie-master, bronindex, bootstrapstatus en maandarchief: `Data/02_Output/Rapportages/Verbruikshistorie/`.\n"
        "- Eerdere locatiebeschrijvingen in historische passages zijn niet leidend voor actuele vragen.\n"
    )
    for relative in _active_doc_relatives(project_root):
        path = project_root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in PATH_REPLACEMENTS:
            updated = updated.replace(old, new)
        if LOCATION_MARKER not in updated:
            updated = updated.rstrip() + location_block + "\n"
        if updated != text:
            temp = path.with_name(f".{path.name}.v3220.tmp")
            temp.write_text(updated, encoding="utf-8")
            os.replace(temp, path)
            changed.append(relative.as_posix())
    return changed


def _cleanup_legacy_archive(project_root: Path) -> None:
    legacy_root = project_root / LEGACY_ARCHIVE_RELATIVE
    if not legacy_root.is_dir():
        return
    try:
        if not any(legacy_root.iterdir()):
            legacy_root.rmdir()
    except OSError:
        pass


def _write_status(project_root: Path, payload: dict[str, Any]) -> None:
    status_path = project_root / STRUCTURE_STATUS_RELATIVE
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp = status_path.with_name(f".{status_path.name}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, status_path)


def migrate_project_structure(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root)
    (project_root / HISTORY_RELATIVE).mkdir(parents=True, exist_ok=True)
    (project_root / HISTORY_ARCHIVE_RELATIVE).mkdir(parents=True, exist_ok=True)

    archive_pairs = _archive_pairs(project_root)
    all_pairs = list(FILE_MOVES) + archive_pairs

    # Een volledig afgeronde migratie is vanaf de tweede start strikt read-only.
    # Alleen wanneer een legacy bron opnieuw is verschenen, wordt de normale
    # fail-closed preflight opnieuw uitgevoerd.
    status_path = project_root / STRUCTURE_STATUS_RELATIVE
    if status_path.is_file():
        try:
            previous = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StructureMigrationConflict(
                f"Bestaande structuurstatus is onleesbaar: {type(exc).__name__}: {exc}"
            ) from exc
        if (
            previous.get("status") == "completed"
            and previous.get("version") == STRUCTURE_VERSION
            and not any((project_root / source_rel).is_file() for source_rel, _ in all_pairs)
        ):
            result = dict(previous)
            result["idempotent"] = True
            return result
    for source_rel, target_rel in all_pairs:
        _preflight_pair(project_root, source_rel, target_rel)

    candidates = _backup_candidates(project_root, archive_pairs)
    manifest = _create_or_verify_backup(project_root, candidates) if candidates else {
        "version": STRUCTURE_VERSION,
        "files": [],
        "status": "not_needed",
    }

    knowledge_base_rehomed = _ensure_writable_knowledge_base(project_root)
    moves = [_copy_verify_remove(project_root, source_rel, target_rel) for source_rel, target_rel in all_pairs]
    _cleanup_legacy_archive(project_root)
    changed_docs = _rewrite_active_docs(project_root)

    payload = {
        "status": "completed",
        "version": STRUCTURE_VERSION,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "backup": STRUCTURE_BACKUP_RELATIVE.as_posix() if manifest.get("files") else None,
        "moves": moves,
        "changed_docs": changed_docs,
        "knowledge_base_rehomed": knowledge_base_rehomed,
        "canonical": {
            "knowledge_base": KNOWLEDGE_BASE_RELATIVE.as_posix(),
            "roadmap": ROADMAP_RELATIVE.as_posix(),
            "history": HISTORY_RELATIVE.as_posix(),
            "master": HISTORY_MASTER_RELATIVE.as_posix(),
            "archive": HISTORY_ARCHIVE_RELATIVE.as_posix(),
        },
    }
    _write_status(project_root, payload)
    _finish_knowledge_base_rehome(project_root, knowledge_base_rehomed)
    return payload
