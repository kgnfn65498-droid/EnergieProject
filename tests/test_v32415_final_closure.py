import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

import conversation_intake as ci
from operating_mode_runtime import _projectmanager_self_audit_check


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _pm_runtime_files(root: Path, *, health: dict, journal: dict | None = None, audit_status='GREEN'):
    audit = root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json'
    status = root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    version = root / 'App/VERSIE.txt'
    _write_json(audit, {'status': audit_status, 'invalid': [], 'warnings': []})
    _write_json(status, {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.15'},
        'health': health,
    })
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.15\n', encoding='utf-8')
    if journal is not None:
        _write_json(root / 'Inbox/atomic_app_swap_state.json', journal)
    # Authoritative self-audit is allowed to be microscopically newer than status.
    stat = status.stat()
    os.utime(audit, (stat.st_atime + 1, stat.st_mtime + 1))


def _stale_atomic_health(extra=None):
    checks = [{
        'name': 'release_atomic_state',
        'status': 'RED',
        'reason': 'live_acceptance_blocks_release_ingress',
        'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'age_seconds': 2784}},
    }]
    checks.extend(extra or [])
    return {'status': 'RED', 'checks': checks}


def _journal(target='32.4.15'):
    return {
        'state': 'LIVE_ACCEPTANCE',
        'from_version': '32.4.14',
        'to_version': target,
        'artifact_sha256': 'synthetic',
    }


def test_stale_live_acceptance_red_is_allowed_only_for_current_release_journal(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health=_stale_atomic_health(), journal=_journal())
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is True


def test_stale_live_acceptance_red_blocks_when_atomic_target_is_wrong(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health=_stale_atomic_health(), journal=_journal('32.4.14'))
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False


def test_stale_live_acceptance_exception_never_hides_other_non_green_health(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health=_stale_atomic_health([{
        'name': 'release_watcher', 'status': 'RED', 'reason': 'watcher_inactive_or_stale'
    }]), journal=_journal())
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False


def test_stale_live_acceptance_exception_requires_valid_journal(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health=_stale_atomic_health(), journal=None)
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False


def test_32415_semantic_approval_variants_are_protected():
    variants = [
        'Maak de architectuur geschikt voor Claude Cowork.',
        'Bouw ondersteuning voor Claude Cowork in de architectuur.',
        'Voeg Claude Cowork toe aan de systeemarchitectuur.',
        'Integreer Claude Cowork in de architectuur.',
        'Koppel Claude Cowork aan de systeemopzet.',
        'Zet deze release in Home Assistant.',
        'Rol deze release uit naar Home Assistant.',
        'Maak deze release actief in Home Assistant.',
        'Voer deze release door in Home Assistant.',
        'Zet deze build op de Green.',
        'Breng deze versie live op Home Assistant.',
    ]
    for text in variants:
        result = ci.classify_intake(text)
        assert result['approval_required'] is True, text


def test_analysis_of_architecture_without_mutation_stays_unprotected():
    assert ci.classify_intake('Analyseer of Claude Cowork later in de architectuur past.')['approval_required'] is False
