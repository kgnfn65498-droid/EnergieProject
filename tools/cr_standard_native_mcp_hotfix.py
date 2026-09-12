#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

TARGETS = (
    'Infra/Docker/native-mcp/crash_recovery.py',
    'Infra/Docker/native-mcp/tools_recovery.py',
    'Infra/Docker/native-mcp/build_nas_container_crash_recovery.sh',
    'Infra/Docker/native-mcp/nas_cr_keep1_retention.sh',
    'Infra/Docker/native-mcp/tests/test_crash_recovery_filename_standard.py',
)
BACKUP_ROOT = 'Backups/MCPHotfix/v32.4.38'
RESULT_REL = 'Inbox/logs/cr_standard_native_mcp_hotfix_v32438.json'


def _replace(text: str, old: str, new: str, label: str, *, count: int | None = 1) -> str:
    if new in text and old not in text:
        return text
    found = text.count(old)
    if found == 0:
        raise RuntimeError(f'{label}: verwachte bronvorm ontbreekt')
    if count is not None and found != count:
        raise RuntimeError(f'{label}: onverwacht aantal bronmatches {found}, verwacht {count}')
    return text.replace(old, new, -1 if count is None else count)


def _crash_recovery(text: str) -> str:
    text = _replace(
        text,
        'CRASH_NAME_SUFFIX = "CrashRecovery EnergieProject"\nCRASH_FILENAME_GLOB = f"* {CRASH_NAME_SUFFIX}*.zip"\nRETENTION_DEFAULT = 3',
        'LEGACY_CRASH_NAME_SUFFIX = "CrashRecovery EnergieProject"\nCRASH_NAME_SUFFIX = "CR EnergieProject"\nCRASH_FILENAME_GLOB = f"* {CRASH_NAME_SUFFIX}*.zip"\nRETENTION_DEFAULT = 1',
        'crash_recovery constants',
    )
    text = _replace(
        text,
        'for pattern in (CRASH_FILENAME_GLOB, f"{CRASH_PREFIX}_*.zip"):',
        'for pattern in (CRASH_FILENAME_GLOB, f"* {LEGACY_CRASH_NAME_SUFFIX}*.zip", f"{CRASH_PREFIX}_*.zip"):',
        'crash_recovery migration discovery',
    )
    text = _replace(text, 'retention: int = 3,', 'retention: int = 1,', 'crash_recovery default retention', count=2)
    old_exclude = 'parts[1] in {CRASH_DIR_NAME, "RestoreStaging", "_release_prepare"}'
    new_exclude = 'parts[1] in {CRASH_DIR_NAME, "CRRetentionQuarantine", "RestoreStaging", "_release_prepare"}'
    if new_exclude not in text and old_exclude in text:
        text = _replace(text, old_exclude, new_exclude, 'project CR quarantine exclusion', count=None)
    text = text.replace(
        '[f"Backups/{CRASH_DIR_NAME}/**"]',
        '[f"Backups/{CRASH_DIR_NAME}/**", "Backups/CRRetentionQuarantine/**"]',
    )
    text = _replace(
        text,
        'base_stem = f"{_local_file_stamp()} {CRASH_NAME_SUFFIX}"',
        'base_stem = f"{_local_file_stamp()} {version} {CRASH_NAME_SUFFIX}"',
        'crash_recovery canonical name',
    )
    if 'energie_cr_retention_quarantine_v1' not in text:
        old = """def _apply_retention(crash_root: Path, retention: int):
    retention = max(1, int(retention))
    zips = sorted(_crash_zip_candidates(crash_root),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for old_zip in zips[retention:]:
        stem = old_zip.name[:-4]
        for item in (
            old_zip,
            crash_root / f\"{stem}.sha256\",
            crash_root / f\"{stem}.manifest.json\",
            crash_root / f\"{stem}.restore.txt\",
        ):
            if item.exists():
                item.unlink()
        removed.append(old_zip.name)
    return removed
"""
        new = """def _external_set_paths(crash_root: Path, zip_path: Path) -> tuple[Path, Path, Path, Path]:
    stem = zip_path.name[:-4]
    return (
        zip_path,
        crash_root / f\"{stem}.sha256\",
        crash_root / f\"{stem}.manifest.json\",
        crash_root / f\"{stem}.restore.txt\",
    )


def _external_set_valid(crash_root: Path, zip_path: Path) -> bool:
    zip_file, sha_file, manifest_file, restore_file = _external_set_paths(crash_root, zip_path)
    if not all(path.is_file() and not path.is_symlink() for path in (zip_file, sha_file, manifest_file, restore_file)):
        return False
    try:
        expected = sha_file.read_text(encoding=\"utf-8\").split()[0]
        return len(expected) == 64 and _sha256_file(zip_file) == expected
    except (OSError, IndexError):
        return False


def _apply_retention(crash_root: Path, retention: int):
    retention = max(1, int(retention))
    zips = sorted(_crash_zip_candidates(crash_root), key=lambda p: p.stat().st_mtime, reverse=True)
    moved = []
    quarantine_root = crash_root.parent / \"CRRetentionQuarantine\" / \"EnergieProject\"
    for old_zip in zips[retention:]:
        if not _external_set_valid(crash_root, old_zip):
            continue
        paths = _external_set_paths(crash_root, old_zip)
        batch = crash_root / f\".cr-retention-stage-{_utc_stamp()}\"
        batch.mkdir()
        staged = []
        try:
            for source in paths:
                destination = batch / source.name
                os.replace(source, destination)
                staged.append((source, destination))
            manifest = {
                \"schema\": \"energie_cr_retention_quarantine_v1\",
                \"type\": \"EnergieProject\",
                \"original_paths\": [str(source) for source, _ in staged],
                \"files\": [destination.name for _, destination in staged],
                \"delete_performed\": False,
            }
            (batch / \"manifest.json\").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + \"\\n\", encoding=\"utf-8\")
            quarantine_root.mkdir(parents=True, exist_ok=True)
            final = quarantine_root / batch.name.removeprefix(\".\")
            os.replace(batch, final)
            moved.append(old_zip.name)
        except Exception:
            for source, destination in reversed(staged):
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
            try:
                (batch / \"manifest.json\").unlink(missing_ok=True)
                batch.rmdir()
            except OSError:
                pass
            raise
    return moved
"""
        text = _replace(text, old, new, 'EnergieProject CR transaction-safe quarantine retention')
    # 32.4.37 truthfulness: moved to quarantine is not deletion.
    if 'removed = _apply_retention(crash_root, retention)' in text:
        text = text.replace(
            'removed = _apply_retention(crash_root, retention)',
            'quarantined = _apply_retention(crash_root, retention)',
            1,
        )
        text = text.replace(
            '"retention_removed": removed,',
            '"retention_removed": [],\n            "retention_quarantined": quarantined,\n            "retention_delete_performed": False,',
            1,
        )
    return text

def _tools_recovery(text: str) -> str:
    text = _replace(text, 'retention=3,', 'retention=1,', 'tools_recovery max-1', count=2)
    if 'energie_native_mcp_runtime_v1' in text:
        return text
    text = _replace(
        text,
        'from pathlib import Path\nfrom typing import Any\n',
        'from pathlib import Path\nfrom typing import Any\nimport hashlib\nimport json\nimport os\nfrom datetime import datetime, timezone\n',
        'native MCP runtime fingerprint imports',
    )
    anchor = """PATHS = RecoveryPaths(
    project_root=PROJECT_ROOT,
    report_root=REPORT_ROOT,
    recovery_root=RECOVERY_ROOT,
)
"""
    marker = anchor + """

def _write_native_mcp_runtime_fingerprint() -> None:
    digest = hashlib.sha256()
    for name in (\"crash_recovery.py\", \"tools_recovery.py\"):
        path = Path(__file__).with_name(name)
        digest.update(name.encode(\"utf-8\") + b\"\\0\")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    target = PROJECT_ROOT / \"Inbox/native_mcp_runtime/runtime_fingerprint.json\"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + f\".tmp-{os.getpid()}\")
    payload = {
        \"schema\": \"energie_native_mcp_runtime_v1\",
        \"fingerprint\": digest.hexdigest(),
        \"loaded_at\": datetime.now(timezone.utc).isoformat(),
    }
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + \"\\n\", encoding=\"utf-8\")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


_write_native_mcp_runtime_fingerprint()
"""
    text = _replace(text, anchor, marker, 'native MCP runtime fingerprint marker')
    return text

def _nas_builder(text: str) -> str:
    text = _replace(
        text,
        'BASE_NAME="${FILESTAMP} CrashRecovery NAS Containers"',
        'BASE_NAME="${FILESTAMP} ${VERSION} CR NAS Containers"',
        'NAS builder canonical name',
    )
    text = _replace(text, "echo 'NAS_CR_RETENTION_KEEP1_OK'", "echo 'NAS_CR_RETENTION_MAX1_OK'", 'NAS builder max-1 marker')
    old = '''# Keep-1 wordt pas uitgevoerd nadat ZIP, restore-preview, interne hashes,
# offline runtimes en de finale SHA allemaal succesvol zijn afgerond.
sh "$RETENTION_HELPER" "$OUTDIR" "$NAME"
'''
    new = '''# Max-1 wordt pas uitgevoerd nadat ZIP, restore-preview, interne hashes,
# offline runtimes en de finale SHA allemaal succesvol zijn afgerond.
echo 'NAS_CR_RETENTION_MAX1_OK' >> "$VERIFY"
sh "$RETENTION_HELPER" "$OUTDIR" "$NAME"
'''
    text = _replace(text, old, new, 'NAS builder retention verification marker')
    return text


def _nas_retention(text: str) -> str:
    text = _replace(
        text,
        'for ZIP_PATH in "$DIR"/*" CrashRecovery NAS Containers"*.zip; do',
        'for ZIP_PATH in "$DIR"/*" CrashRecovery NAS Containers"*.zip "$DIR"/*" CR NAS Containers"*.zip; do',
        'NAS retention migration discovery',
    )
    text = _replace(
        text,
        'validate_set() {\n  STEM="$1"\n  set_paths "$STEM"',
        'validate_set() {\n  STEM="$1"\n  REQUIRE_MAX1="${2:-0}"\n  set_paths "$STEM"',
        'NAS retention validation mode',
    )
    text = _replace(
        text,
        "  grep -q '^NAS_CONTAINER_CR_ACCEPTANCE_OK$' \"$VERIFY\" 2>/dev/null || return 1\n  return 0",
        "  grep -q '^NAS_CONTAINER_CR_ACCEPTANCE_OK$' \"$VERIFY\" 2>/dev/null || return 1\n  grep -q '^PRODUCTION_CONTAINERS_CHANGED=NO$' \"$VERIFY\" 2>/dev/null || return 1\n  if [ \"$REQUIRE_MAX1\" -eq 1 ]; then grep -q '^NAS_CR_RETENTION_MAX1_OK$' \"$VERIFY\" 2>/dev/null || return 1; fi\n  return 0",
        'NAS retention acceptance proof',
    )
    text = _replace(
        text,
        'validate_set "$NEW_STEM" || fail',
        'validate_set "$NEW_STEM" 1 || fail',
        'NAS retention new-set max-1 proof',
        count=2,
    )
    if 'CRRetentionQuarantine' not in text:
        old = """  rm -f \\
    \"$BATCH/$STEM.zip\" \\
    \"$BATCH/$STEM.zip.sha256\" \\
    \"$BATCH/$STEM VERIFY.txt\" || fail \"oude set kon niet definitief worden verwijderd: $STEM\"
  rmdir \"$BATCH\" || fail \"tijdelijke retentiemap bleef achter: $BATCH\"
"""
        new = """  QROOT=\"$(dirname \"$DIR\")/CRRetentionQuarantine/NAS Container\"
  QDEST=\"$QROOT/$(date '+%Y%m%dT%H%M%S')-$$-$REMOVED\"
  printf '%s\\n' \\
    'schema=energie_cr_retention_quarantine_v1' \\
    'type=NAS Containers' \\
    \"source=$DIR\" \\
    \"stem=$STEM\" \\
    'delete_performed=false' > \"$BATCH/manifest.txt\" || fail \"retentie-manifest kon niet worden geschreven: $STEM\"
  mkdir -p \"$QROOT\" || fail \"retentiequarantaine kon niet worden gemaakt\"
  mv \"$BATCH\" \"$QDEST\" || fail \"oude set kon niet naar retentiequarantaine: $STEM\"
"""
        text = _replace(text, old, new, 'NAS retention quarantine instead of delete')
    return text

def _native_test(text: str) -> str:
    text = _replace(text, 'retention=3,', 'retention=1,', 'native CR test retention')
    text = _replace(
        text,
        'r"^\\d{4}-\\d{2}-\\d{2} \\d{2}\\.\\d{2} CrashRecovery EnergieProject(?: \\(\\d+\\))?\\.zip$"',
        'r"^\\d{4}-\\d{2}-\\d{2} \\d{2}\\.\\d{2} 32\\.3\\.39 CR EnergieProject(?: \\(\\d+\\))?\\.zip$"',
        'native CR test canonical name',
    )
    text = _replace(
        text,
        'self.assertEqual(list_crash_recovery_backups(recovery)["count"], 3)',
        'self.assertEqual(list_crash_recovery_backups(recovery)["count"], 1)',
        'native CR test max-1 count',
    )
    return text


TRANSFORMS: dict[str, Callable[[str], str]] = {
    TARGETS[0]: _crash_recovery,
    TARGETS[1]: _tools_recovery,
    TARGETS[2]: _nas_builder,
    TARGETS[3]: _nas_retention,
    TARGETS[4]: _native_test,
}


def _atomic_write(path: Path, text: str) -> None:
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(text, encoding='utf-8')
        os.chmod(temp, path.stat().st_mode & 0o7777)
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _validate(path: Path, text: str) -> None:
    if path.suffix == '.py':
        compile(text, str(path), 'exec')
    elif path.suffix == '.sh':
        completed = subprocess.run(['sh', '-n', str(path)], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f'shellsyntax RED voor {path.name}: {completed.stderr.strip()}')


def _contract_predicates(root: Path | str) -> dict[str, bool]:
    root = Path(root).resolve()
    def read(rel: str) -> str:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            return ''
        return path.read_text(encoding='utf-8', errors='replace')

    crash = read(TARGETS[0])
    tools = read(TARGETS[1])
    builder = read(TARGETS[2])
    retention = read(TARGETS[3])
    native_test = read(TARGETS[4])
    return {
        'project_retention_max1': 'RETENTION_DEFAULT = 1' in crash and crash.count('retention: int = 1,') >= 2,
        'project_runtime_version_in_name': 'base_stem = f"{_local_file_stamp()} {version} {CRASH_NAME_SUFFIX}"' in crash,
        'project_quarantine_first': 'CRRetentionQuarantine' in crash and 'retention_delete_performed' in crash,
        'nas_runtime_version_in_name': '${VERSION} CR NAS Containers' in builder,
        'nas_retention_max1_marker': 'NAS_CR_RETENTION_MAX1_OK' in builder and 'NAS_CR_RETENTION_MAX1_OK' in retention,
        'nas_quarantine_first': 'CRRetentionQuarantine' in retention and 'delete_performed=false' in retention,
        'native_runtime_fingerprint_present': 'energie_native_mcp_runtime_v1' in tools,
        'native_test_retention_max1': 'retention=1,' in native_test and 'list_crash_recovery_backups(recovery)["count"], 1' in native_test,
    }


def _preflight_transforms(root: Path) -> list[dict[str, str]]:
    """Transform exact live source in memory and prove syntax before writes."""
    evidence = []
    for rel in TARGETS:
        target = root / rel
        if not target.is_file() or target.is_symlink():
            raise RuntimeError(f'begrensd native-MCP doel ontbreekt/onveilig: {rel}')
        old = target.read_text(encoding='utf-8')
        new = TRANSFORMS[rel](old)
        if target.suffix == '.py':
            compile(new, str(target), 'exec')
        elif target.suffix == '.sh':
            check = subprocess.run(['sh', '-n'], input=new, capture_output=True, text=True, check=False)
            if check.returncode != 0:
                raise RuntimeError(f'preflight shellsyntax RED voor {target.name}: {check.stderr.strip()}')
        evidence.append({
            'path': rel,
            'source_sha256': hashlib.sha256(old.encode('utf-8')).hexdigest(),
            'transformed_sha256': hashlib.sha256(new.encode('utf-8')).hexdigest(),
            'transform_idempotent': str(new == old).lower(),
        })
    return evidence


def apply(root: Path) -> dict:
    root = Path(root).resolve()
    backup_root = root / BACKUP_ROOT
    result_path = root / RESULT_REL
    changes: list[dict[str, str]] = []
    changed_paths: list[Path] = []
    preflight: list[dict[str, str]] = []
    predicates: dict[str, bool] = {}
    try:
        preflight = _preflight_transforms(root)
        for rel in TARGETS:
            target = root / rel
            if not target.is_file() or target.is_symlink():
                raise RuntimeError(f'begrensd native-MCP doel ontbreekt/onveilig: {rel}')
            old = target.read_text(encoding='utf-8')
            new = TRANSFORMS[rel](old)
            if new == old:
                changes.append({'path': rel, 'status': 'already_migrated'})
                continue
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(target, backup)
            _atomic_write(target, new)
            _validate(target, new)
            changed_paths.append(target)
            changes.append({'path': rel, 'status': 'changed', 'backup': str(backup.relative_to(root))})

        # Contract-level assertions after all bounded edits. Every predicate is
        # named in evidence so a future RED points to the exact broken contract.
        # Backward-readable definitions: 'CRRetentionQuarantine' in crash;
        # 'energie_native_mcp_runtime_v1' in tools; 'CRRetentionQuarantine' in retention.
        predicates = _contract_predicates(root)
        failed_predicates = [name for name, ok in predicates.items() if ok is not True]
        if failed_predicates:
            raise RuntimeError('native-MCP CR standaard postcheck RED: ' + ','.join(failed_predicates))
        result = {
            'schema': 'energie_cr_standard_native_mcp_hotfix_v32438',
            'status': 'GREEN',
            'ok': True,
            'targets': list(TARGETS),
            'changes': changes,
            'source_transform_preflight': preflight,
            'predicates': predicates,
            'failed_predicates': [],
            'mcp_restart_required': any(str(path).endswith(('crash_recovery.py', 'tools_recovery.py')) for path in changed_paths),
            'restart_performed': False,
            'finished_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        # Roll back only files changed by this invocation, from the first preserved backup.
        for target in reversed(changed_paths):
            rel = target.relative_to(root).as_posix()
            backup = backup_root / rel
            if backup.is_file():
                shutil.copy2(backup, target)
        result = {
            'schema': 'energie_cr_standard_native_mcp_hotfix_v32438',
            'status': 'RED',
            'ok': False,
            'error': str(exc),
            'changes': changes,
            'source_transform_preflight': preflight,
            'predicates': _contract_predicates(root),
            'failed_predicates': [name for name, ok in _contract_predicates(root).items() if ok is not True],
            'mcp_restart_required': False,
            'restart_performed': False,
            'finished_at': datetime.now(timezone.utc).isoformat(),
        }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        raise
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Bounded 32.4.38 native-MCP CR/runtime/retention migration')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    try:
        result = apply(Path(args.root))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(f'CR_STANDARD_NATIVE_MCP_HOTFIX_RED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
