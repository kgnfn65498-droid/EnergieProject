def nomad_context(manager_snapshot: dict) -> dict:
    return {
        'project': manager_snapshot.get('project_id', 'energie'),
        'mode': manager_snapshot.get('mode'),
        'health': manager_snapshot.get('health'),
        'active_task': manager_snapshot.get('active_task'),
        'decisions_needed': manager_snapshot.get('decisions_needed', []),
    }


def parent_manager_summary(manager_snapshot: dict) -> dict:
    return {
        'project_id': manager_snapshot.get('project_id', 'energie'),
        'mode': manager_snapshot.get('mode'),
        'health': manager_snapshot.get('health'),
        'needs_human': bool(manager_snapshot.get('decisions_needed')),
    }
