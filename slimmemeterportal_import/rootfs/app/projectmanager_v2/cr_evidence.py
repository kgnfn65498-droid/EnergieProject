EXPECTED_SCOPE = {'EnergieProject', 'NAS/Containers', 'Home Assistant'}


def evaluate_cr_closure(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {'status': 'ORANGE', 'reason': 'closure_missing_or_invalid', 'evidence_strength': 'unverified'}
    if payload.get('status') != 'GREEN_PRACTICAL_ACCEPTANCE_COMPLETE':
        return {'status': 'ORANGE', 'reason': 'closure_status_not_canonical_green', 'evidence_strength': 'unverified'}
    if set(payload.get('scope') or []) != EXPECTED_SCOPE:
        return {'status': 'ORANGE', 'reason': 'closure_scope_incomplete', 'evidence_strength': 'unverified'}

    evidence = payload.get('evidence') or {}
    project = evidence.get('EnergieProject') or {}
    nas = evidence.get('NAS_Containers') or {}
    ha = evidence.get('Home_Assistant') or {}

    project_ok = (
        project.get('zip_integrity') == 'ok'
        and isinstance(project.get('deep_verified_files'), int)
        and project.get('deep_verified_files') == project.get('manifest_file_count')
        and project.get('hash_failures') == 0
    )
    nas_ok = (
        nas.get('zip_integrity') == 'ok'
        and nas.get('restore_extract') == 'ok'
        and nas.get('image_create_remove') == '4/4 ok'
        and nas.get('production_containers_changed') is False
    )
    ha_ok = (
        ha.get('backup_manager_state_after_run') == 'idle'
        and bool(ha.get('fresh_backup_event_seen_utc'))
        and 'confirmed' in str(ha.get('external_backup_file', '')).lower()
    )
    external_ok = 'confirmed' in str(payload.get('external_storage', '')).lower()

    if all((project_ok, nas_ok, ha_ok, external_ok)):
        return {
            'status': 'GREEN',
            'reason': 'practical_three_domain_acceptance_verified',
            'evidence_strength': 'verified',
        }
    return {
        'status': 'ORANGE',
        'reason': 'closure_evidence_incomplete',
        'evidence_strength': 'partial',
        'details': {
            'project_ok': project_ok,
            'nas_ok': nas_ok,
            'home_assistant_ok': ha_ok,
            'external_storage_ok': external_ok,
        },
    }
