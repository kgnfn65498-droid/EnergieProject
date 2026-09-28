from __future__ import annotations

"""32.5.26 audit of the *original* five-bucket ClearUp Type-3 rubric.

Type-3 means: items that originally required dependency/runtime classification.
It is deliberately not an alias for generic project hygiene debt. Most original
Type-3 sources were subsequently resolved by Type-2 002-012 and now have a
canonical destination. This service proves that state and exposes the one
remaining legacy source, which the final Inbox cleanup handles after its writer
has been rebound in 32.5.26.
"""

import json
from pathlib import Path
from typing import Any

from system_path_contract import project_system_path

TYPE3_MIN_RELEASE = (32, 5, 26)

ORIGINAL_TYPE3: tuple[dict[str, Any], ...] = (
    {"source":"Inbox/.nas-container-cr.operation.lock", "destination":"Data/03_Systeem/Projectmanager/Runtime/Locks/nas-container-cr.operation.lock", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/.release-controller.lock", "destination":"Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/.release-transition.operation.lock", "destination":"Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/watcher_heartbeat.v2", "destination":"Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_heartbeat.v2", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/atomic_app_swap_state.json", "destination":"Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/github_publication_state.json", "destination":"Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/github_publisher_state.json", "destination":"Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/project_cr_local", "destination":"Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/nas_container_cr_local", "destination":"Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal", "resolved_as":"TYPE4_TO_TYPE2"},
    {"source":"Inbox/crash_recovery_cleanup_result.json", "destination":"Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup/result.json", "resolved_as":"TYPE4_REBIND_32_5_26"},
    {"source":"Inbox/control_plane/watcher_recreate_result.json", "destination":"Data/03_Systeem/Projectmanager/ControlPlane/Runtime/results/watcher_recreate.json", "resolved_as":"TYPE1_OBSOLETE"},
    {"source":"Inbox/process", "destination":"Data/03_Systeem/Projectmanager/Runtime/Process", "resolved_as":"TYPE2"},
    {"source":"Inbox/.watcher.heartbeat", "destination":"Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher.heartbeat.legacy", "resolved_as":"TYPE2"},
)


def _version_tuple(value: str) -> tuple[int, ...]:
    try: return tuple(int(part) for part in str(value).split('.'))
    except ValueError: return ()


def _json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeError): return {}


def _release_version(root: Path) -> str:
    p=root/'App/VERSIE.txt'
    if p.is_symlink() or not p.is_file(): raise RuntimeError('Type3 active release missing/unsafe')
    version=p.read_text(encoding='utf-8').strip()
    if _version_tuple(version)<TYPE3_MIN_RELEASE: raise RuntimeError('Type3 requires active 32.5.26+')
    return version


def _release_idle(root: Path, version: str) -> None:
    controller=_json(root/'Data/03_Systeem/Projectmanager/ReleaseController/current.json')
    if not controller: controller=_json(project_system_path(root,'Inbox/release_controller/current.json'))
    if str(controller.get('status') or '').upper()!='COMPLETE' or str(controller.get('phase') or '').upper()!='COMPLETE':
        raise RuntimeError('Type3 requires COMPLETE release controller')
    if str(controller.get('to_version') or version) not in {'',version}:
        raise RuntimeError('Type3 controller release mismatch')
    processing=root/'Inbox/processing'
    if processing.exists() and (processing.is_symlink() or not processing.is_dir()): raise RuntimeError('unsafe processing path')
    if processing.is_dir() and any(p.is_file() and not p.is_symlink() for p in processing.iterdir()):
        raise RuntimeError('Type3 refuses active processing release')


def _present(path: Path) -> bool:
    return path.exists() and not path.is_symlink()


def inventory_type3(project_root: Path | str) -> dict[str, Any]:
    root=Path(project_root).resolve(); version=_release_version(root); _release_idle(root,version)
    items=[]; pending=[]; resolved=[]
    for spec in ORIGINAL_TYPE3:
        source=root/spec['source']; destination=root/spec['destination']
        source_present=_present(source); destination_present=_present(destination)
        state='PENDING_LEGACY_SOURCE' if source_present else 'RESOLVED_SOURCE_ABSENT'
        # TYPE1 had no required destination. The crash cleanup source is expected
        # to remain pending until final Inbox cleanup quarantines the stale result.
        if spec['resolved_as']!='TYPE1_OBSOLETE' and not destination_present:
            state='DESTINATION_MISSING' if not source_present else 'PENDING_LEGACY_SOURCE_DESTINATION_MISSING'
        row={**spec,'source_present':source_present,'destination_present':destination_present,'state':state}
        items.append(row)
        if source_present: pending.append(spec['source'])
        elif state.startswith('RESOLVED'): resolved.append(spec['source'])
    missing_destinations=[x['destination'] for x in items if x['resolved_as']!='TYPE1_OBSOLETE' and not x['destination_present']]
    # The canonical Cleanup directory itself is enough before the first 32.5.26
    # cleanup request/result is emitted; a stale historical Inbox result is not
    # copied into canonical active state.
    cleanup_dir=root/'Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup'
    if cleanup_dir.is_dir() and 'Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup/result.json' in missing_destinations:
        missing_destinations.remove('Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup/result.json')
    status='GREEN' if not missing_destinations else 'RED'
    return {
        'schema':'energie_clearup_original_type3_inventory_v1',
        'status':status,
        'classification':'TYPE3_ORIGINAL_RUBRIC',
        'release_version':version,
        'item_count':len(ORIGINAL_TYPE3),
        'resolved_count':len(resolved),
        'pending_legacy_sources':sorted(pending),
        'missing_canonical_destinations':sorted(missing_destinations),
        'items':items,
        'generic_project_hygiene_is_separate':True,
        'next_action':'run final Inbox cleanup after all 32.5.26 canonical writer bindings are active',
        'delete_capability':False,
    }


def apply_type3(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    """Compatibility command: original Type-3 cleanup is completed by final Inbox cleanup.

    Do not run the old generic project-clearup engine under the Type-3 label.
    """
    inv=inventory_type3(project_root)
    return {**inv,'status':'ROUTED_TO_FINAL_INBOX_CLEANUP','executed':False,
            'reason':'original_type3_is_classification_audit; use inbox_cleanup_apply for remaining legacy sources'}


def restore_type3(project_root: Path | str, *, run_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    return {'status':'NOT_APPLICABLE','executed':False,'reason':'original Type-3 inventory performs no move; restore belongs to final Inbox cleanup manifest','run_id':str(run_id or '')}
