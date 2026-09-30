from __future__ import annotations

from pathlib import Path
from typing import Any


def discover_capabilities(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    def present(rel: str) -> bool:
        p = root / rel
        return p.is_file() and not p.is_symlink()
    rows = [
        {
            'key': 'clearup_type1',
            'status': 'ACTIVE',
            'first_proven_release': '32.5.3',
            'executor': '32.5.x privileged sideband',
            'files': [
                'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_chat_service.py',
                'App/tools/project_clearup_move_executor.py',
                'App/tools/sideband_bridge.py',
            ],
        },
        {
            'key': 'clearup_type2_002_012',
            'status': 'CLOSED_GREEN',
            'first_proven_release': '32.5.7',
            'request_scoped_from': '32.5.18/32.5.19',
            'executor': '32.5.x privileged sideband',
            'files': [
                'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_type2_service.py',
                'App/tools/project_clearup_move_executor.py',
                'App/tools/sideband_bridge.py',
            ],
        },
        {
            'key': 'clearup_type3_final_inbox',
            'status': 'ACTIVE' if present('App/slimmemeterportal_import/rootfs/app/projectmanager_v2/inbox_cleanup_32526.py') else 'MISSING',
            'first_proven_release': '32.5.26',
            'executor': '32.5.x privileged sideband',
            'files': [
                'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_type3_service.py',
                'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/inbox_cleanup_32526.py',
                'App/tools/project_clearup_move_executor.py',
                'App/tools/sideband_bridge.py',
            ],
        },
        {
            'key': 'project_clearup_auto_32_4',
            'status': 'FORBIDDEN_HISTORICAL',
            'executor': 'legacy 32.4 startup-auto route',
            'files': ['App/slimmemeterportal_import/rootfs/app/project_clearup_auto.py'],
            'reason': 'must not be reactivated for 32.5.26 Type-3/final Inbox cleanup',
        },
    ]
    for row in rows:
        row['files_present'] = {rel: present(rel) for rel in row['files']}
        if row.get('status') != 'FORBIDDEN_HISTORICAL' and not all(row['files_present'].values()):
            row['declared_status'] = row.get('status')
            row['status'] = 'MISSING'
            row['reason'] = 'declared capability is not fully present in live code'
    return {
        'schema': 'energie_projectmanager_capability_registry_v2',
        'status': 'GREEN' if all(row['status'] != 'MISSING' for row in rows) else 'RED',
        'source_of_truth': 'live code presence + historical provenance labels',
        'capabilities': rows,
        'must_consult_before_unavailable_conclusion': True,
    }
