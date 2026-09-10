#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
BACKUP_ROOT = 'Backups/MCPHotfix/v32.4.36'
RESULT_REL = 'Inbox/logs/cr_standard_native_mcp_hotfix_v32436.json'


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
    text = _replace(
        text,
        'base_stem = f"{_local_file_stamp()} {CRASH_NAME_SUFFIX}"',
        'base_stem = f"{_local_file_stamp()} {version} {CRASH_NAME_SUFFIX}"',
        'crash_recovery canonical name',
    )
    return text


def _tools_recovery(text: str) -> str:
    return _replace(text, 'retention=3,', 'retention=1,', 'tools_recovery max-1', count=2)


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


def apply(root: Path) -> dict:
    root = Path(root).resolve()
    backup_root = root / BACKUP_ROOT
    result_path = root / RESULT_REL
    changes: list[dict[str, str]] = []
    changed_paths: list[Path] = []
    try:
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

        # Contract-level assertions after all bounded edits.
        crash = (root / TARGETS[0]).read_text(encoding='utf-8')
        tools = (root / TARGETS[1]).read_text(encoding='utf-8')
        builder = (root / TARGETS[2]).read_text(encoding='utf-8')
        retention = (root / TARGETS[3]).read_text(encoding='utf-8')
        required = (
            'RETENTION_DEFAULT = 1' in crash,
            ' CR EnergieProject' in crash,
            'retention=1,' in tools,
            '${VERSION} CR NAS Containers' in builder,
            'NAS_CR_RETENTION_MAX1_OK' in builder,
            ' CR NAS Containers' in retention,
        )
        if not all(required):
            raise RuntimeError('native-MCP CR standaard postcheck RED')
        result = {
            'schema': 'energie_cr_standard_native_mcp_hotfix_v32436',
            'status': 'GREEN',
            'ok': True,
            'targets': list(TARGETS),
            'changes': changes,
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
            'schema': 'energie_cr_standard_native_mcp_hotfix_v32436',
            'status': 'RED',
            'ok': False,
            'error': str(exc),
            'changes': changes,
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
    parser = argparse.ArgumentParser(description='Bounded 32.4.36 native-MCP CR standard migration')
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
