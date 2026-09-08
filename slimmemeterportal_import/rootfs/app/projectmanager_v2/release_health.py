
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
    checks.append(_check(
        'release_incoming',
        'ORANGE' if incoming_count else 'GREEN',
        'release_waiting_incoming' if incoming_count else 'incoming_empty',
        incoming,
    ))

    processing = chain.get('processing') or {}
    stuck = int(processing.get('stuck_count') or 0)
    checks.append(_check(
        'release_processing',
        'RED' if stuck else 'GREEN',
        'stuck_release_present' if stuck else 'no_stuck_release',
        processing,
    ))

    lock = chain.get('installer_lock') or {}
    checks.append(_check(
        'release_installer_lock',
        'ORANGE' if lock.get('active') else 'GREEN',
        'installer_active' if lock.get('active') else 'installer_idle',
        lock,
    ))

    atomic = chain.get('atomic_swap') or {}
    atomic_state = str(atomic.get('state') or '').strip().upper()
    transitional = atomic_state in {'PREPARED', 'OLD_RENAMED', 'NEW_ACTIVE', 'LIVE_ACCEPTANCE'}
    checks.append(_check(
        'release_atomic_state',
        'ORANGE' if (lock.get('active') or transitional) else 'GREEN',
        'installer_or_atomic_transition_active' if (lock.get('active') or transitional) else 'settled',
        {'installer_lock': lock, 'atomic_swap': atomic},
    ))

    publisher = chain.get('publisher') or {}
    publisher_status = str(publisher.get('status') or '').strip().lower()
    publisher_bad = publisher_status in {'error', 'failed', 'blocked'}
    checks.append(_check(
        'release_publisher',
        'RED' if publisher_bad else 'GREEN',
        'publisher_error' if publisher_bad else ('publisher_status_available' if publisher_status else 'no_publisher_error'),
        publisher,
    ))

    publication = chain.get('github_publication') or {}
    publication_status = str(publication.get('status') or '').strip().lower()
    publication_bad = publication_status in {'error', 'failed', 'blocked'}
    publication_pending = publication.get('contract_pending') is True and publication_status != 'published'
    checks.append(_check(
        'release_github_publication',
        'RED' if publication_bad else ('ORANGE' if publication_pending else 'GREEN'),
        'github_publication_error' if publication_bad else (
            'github_publication_pending' if publication_pending else 'github_publication_settled'
        ),
        publication,
    ))

    release = (runtime or {}).get('release') or {}
    rollback_known = 'rollback_version' in release or 'rollback_versions' in release
    rollback_versions = list(release.get('rollback_versions') or [])
    rollback_version = release.get('rollback_version') or (rollback_versions[0] if rollback_versions else None)
    checks.append(_check(
        'release_rollback',
        'GREEN' if (rollback_version or not rollback_known) else 'RED',
        'rollback_available' if rollback_version else (
            'rollback_not_reported_by_legacy_runtime' if not rollback_known else 'rollback_missing'
        ),
        {'rollback_version': rollback_version, 'rollback_versions': rollback_versions},
    ))

    alignment_known = 'nas_version' in release or 'ha_runtime_version' in release
    ha_runtime = release.get('ha_runtime_version') or release.get('version')
    nas_version = release.get('nas_version')
    if not alignment_known:
        alignment_status = 'GREEN'
        alignment_reason = 'runtime_alignment_not_reported_by_legacy_runtime'
    elif not ha_runtime:
        alignment_status = 'RED'
        alignment_reason = 'ha_runtime_unknown'
    elif nas_version and nas_version != ha_runtime:
        alignment_status = 'ORANGE'
        alignment_reason = 'nas_update_not_yet_active_in_ha'
    else:
        alignment_status = 'GREEN'
        alignment_reason = 'nas_and_ha_runtime_aligned'
    checks.append(_check(
        'release_runtime_alignment',
        alignment_status,
        alignment_reason,
        {
            'ha_runtime_version': ha_runtime,
            'nas_version': nas_version,
            'available_update': release.get('available_update'),
        },
    ))
    return checks
