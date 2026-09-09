def _check(name, status, reason, details):
    return {
        'name': name,
        'status': status,
        'reason': reason,
        'details': details or {},
        'evidence_ref': None,
        'evidence_strength': 'verified' if status == 'GREEN' else 'unverified',
    }


def release_health_checks(runtime: dict) -> list:
    chain = (runtime or {}).get('release_chain')
    if not isinstance(chain, dict):
        return []
    checks = []
    watcher = chain.get('watcher') or {}
    checks.append(_check(
        'release_watcher',
        'GREEN' if watcher.get('active') is True else 'RED',
        'heartbeat_fresh' if watcher.get('active') is True else 'watcher_inactive_or_stale',
        watcher,
    ))

    incoming = chain.get('incoming') or {}
    incoming_count = int(incoming.get('count') or 0)
    incoming_status = 'RED' if incoming_count > 1 else ('ORANGE' if incoming_count == 1 else 'GREEN')
    incoming_reason = (
        'multiple_releases_block_ingress' if incoming_count > 1
        else ('release_waiting_incoming' if incoming_count == 1 else 'incoming_empty')
    )
    checks.append(_check('release_incoming', incoming_status, incoming_reason, incoming))

    processing = chain.get('processing') or {}
    stuck = int(processing.get('stuck_count') or 0)
    checks.append(_check(
        'release_processing',
        'RED' if stuck else 'GREEN',
        'stuck_release_present' if stuck else 'no_stuck_release',
        processing,
    ))

    lock = chain.get('installer_lock') or {}
    lock_age = lock.get('age_seconds')
    lock_stale = lock.get('active') is True and lock_age is not None and float(lock_age) >= 600
    checks.append(_check(
        'release_installer_lock',
        'RED' if lock_stale else ('ORANGE' if lock.get('active') else 'GREEN'),
        'installer_lock_stale' if lock_stale else ('installer_active' if lock.get('active') else 'installer_idle'),
        lock,
    ))

    atomic = chain.get('atomic_swap') or {}
    atomic_state = str(atomic.get('state') or '').strip().upper()
    atomic_age = atomic.get('age_seconds')
    atomic_age = float(atomic_age) if atomic_age is not None else None
    terminal_states = {'ACCEPTED', 'ROLLED_BACK'}
    transition_states = {'PREPARED', 'OLD_RENAMED', 'NEW_ACTIVE', 'LIVE_ACCEPTANCE'}
    if not atomic.get('exists', bool(atomic_state)) or not atomic_state:
        atomic_status, atomic_reason = 'ORANGE', 'atomic_state_missing'
    elif atomic_state not in terminal_states | transition_states:
        atomic_status, atomic_reason = 'RED', 'atomic_state_unknown'
    elif atomic_state == 'LIVE_ACCEPTANCE' and (incoming_count > 0 or (atomic_age is not None and atomic_age >= 120)):
        atomic_status, atomic_reason = 'RED', 'live_acceptance_blocks_release_ingress'
    elif atomic_state in transition_states and atomic_age is not None and atomic_age >= 600:
        atomic_status, atomic_reason = 'RED', 'atomic_transition_stale'
    elif atomic_state in transition_states or lock.get('active'):
        atomic_status, atomic_reason = 'ORANGE', 'installer_or_atomic_transition_active'
    else:
        atomic_status, atomic_reason = 'GREEN', 'settled'
    checks.append(_check(
        'release_atomic_state', atomic_status, atomic_reason,
        {'installer_lock': lock, 'atomic_swap': atomic},
    ))

    release = (runtime or {}).get('release') or {}
    current_release = str(release.get('version') or release.get('nas_version') or '').strip()

    publisher = chain.get('publisher') or {}
    publisher_status = str(publisher.get('status') or '').strip().lower()
    publisher_version = str(publisher.get('version') or '').strip()
    publisher_bad = publisher_status in {'error', 'failed', 'blocked'}
    publisher_good = publisher_status in {'published', 'success', 'ok'}
    publisher_is_stale_previous = bool(
        current_release and publisher_version and publisher_version != current_release
    )
    if publisher_is_stale_previous:
        publisher_health, publisher_reason = 'GREEN', 'stale_previous_publisher_state_ignored'
    elif publisher_bad:
        publisher_health, publisher_reason = 'RED', 'publisher_error'
    elif publisher_good:
        publisher_health, publisher_reason = 'GREEN', 'publisher_status_available'
    else:
        publisher_health, publisher_reason = 'ORANGE', 'publisher_status_missing_or_unknown'
    checks.append(_check('release_publisher', publisher_health, publisher_reason, publisher))

    publication = chain.get('github_publication') or {}
    publication_status = str(publication.get('status') or '').strip().lower()
    publication_version = str(publication.get('version') or '').strip()
    publication_bad = publication_status in {'error', 'failed', 'blocked'}
    publication_good = publication_status in {'published', 'success', 'ok'}
    # An open contract is authoritative proof that the current publication
    # transaction is not settled yet. A stale or even current saved success
    # may not bypass an uncleared publication_required marker.
    publication_pending = publication.get('contract_pending') is True
    publication_is_stale_previous = bool(
        current_release
        and publication_version
        and publication_version != current_release
        and not publication_pending
    )
    if publication_pending:
        publication_health, publication_reason = 'ORANGE', 'github_publication_pending'
    elif publication_is_stale_previous:
        publication_health, publication_reason = 'GREEN', 'stale_previous_publication_state_ignored'
    elif publication_bad:
        publication_health, publication_reason = 'RED', 'github_publication_error'
    elif publication_good:
        publication_health, publication_reason = 'GREEN', 'github_publication_settled'
    else:
        publication_health, publication_reason = 'ORANGE', 'github_publication_status_missing_or_unknown'
    checks.append(_check('release_github_publication', publication_health, publication_reason, publication))

    rollback_known = 'rollback_version' in release or 'rollback_versions' in release
    rollback_versions = list(release.get('rollback_versions') or [])
    rollback_version = release.get('rollback_version') or (rollback_versions[0] if rollback_versions else None)
    checks.append(_check(
        'release_rollback',
        'GREEN' if rollback_version else ('ORANGE' if not rollback_known else 'RED'),
        'rollback_available' if rollback_version else (
            'rollback_not_reported_by_legacy_runtime' if not rollback_known else 'rollback_missing'
        ),
        {'rollback_version': rollback_version, 'rollback_versions': rollback_versions},
    ))

    alignment_known = 'nas_version' in release or 'ha_runtime_version' in release
    ha_runtime = release.get('ha_runtime_version') or release.get('version')
    nas_version = release.get('nas_version')
    if not alignment_known:
        alignment_status = 'ORANGE'
        alignment_reason = 'runtime_alignment_not_reported_by_legacy_runtime'
    elif not ha_runtime:
        alignment_status = 'RED'
        alignment_reason = 'ha_runtime_unknown'
    elif not nas_version:
        alignment_status = 'ORANGE'
        alignment_reason = 'nas_runtime_unknown'
    elif nas_version != ha_runtime:
        alignment_status = 'ORANGE'
        alignment_reason = 'nas_update_not_yet_active_in_ha'
    else:
        alignment_status = 'GREEN'
        alignment_reason = 'nas_and_ha_runtime_aligned'
    checks.append(_check(
        'release_runtime_alignment', alignment_status, alignment_reason,
        {
            'ha_runtime_version': ha_runtime,
            'nas_version': nas_version,
            'available_update': release.get('available_update'),
        },
    ))
    return checks
