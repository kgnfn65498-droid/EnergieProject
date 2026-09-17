from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

import operating_mode_runtime as mode_runtime
from release_validation_hold import activate_release_hold, record_hold_validation


def _json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')


def _pm_pair(root: Path, *, generation: str, audit_generation: str | None = None, updated_at: str = '2026-09-15T14:00:00+00:00') -> None:
    version = root / 'App/VERSIE.txt'
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.55\n', encoding='utf-8')
    status = {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.55'},
        'health': {'status': 'GREEN', 'checks': []},
        'cycle_generation': generation,
        'updated_at': updated_at,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
    }
    audit_gen = audit_generation if audit_generation is not None else generation
    audit = {
        'status': 'GREEN',
        'invalid': [],
        'warnings': [],
        'cycle_generation': audit_gen,
        'status_updated_at': updated_at,
        'provenance': {'generation': audit_gen, 'phase': 'FINAL'},
    }
    _json(root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json', status)
    _json(root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json', audit)


def test_temporary_generation_mismatch_fails_closed_then_next_final_pair_is_accepted(tmp_path: Path) -> None:
    _pm_pair(tmp_path, generation='new', audit_generation='old')
    first = mode_runtime._projectmanager_self_audit_check(tmp_path)
    assert first['ok'] is False
    assert 'generation mismatch' in first['detail']

    _pm_pair(tmp_path, generation='new')
    second = mode_runtime._projectmanager_self_audit_check(tmp_path)
    assert second['ok'] is True
    assert 'GREEN' in second['detail']


def test_repeated_identical_blocked_hold_validation_does_not_rewrite_state(tmp_path: Path) -> None:
    activate_release_hold(tmp_path, '32.4.55', 'release_install')
    checks = {'projectmanager_self_audit': {'ok': False, 'detail': 'generation mismatch'}}
    record_hold_validation(tmp_path, '32.4.55', checks, 'ok')
    path = tmp_path / 'Inbox/operating_mode/release_validation_hold.json'
    before = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    # Ensure a rewrite would get a distinguishable mtime on coarse/fast filesystems.
    time.sleep(0.01)
    for _ in range(100):
        record_hold_validation(tmp_path, '32.4.55', checks, 'ok')

    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == before_mtime


def test_hold_validation_changes_once_when_new_evidence_arrives_then_stabilizes(tmp_path: Path) -> None:
    activate_release_hold(tmp_path, '32.4.55', 'release_install')
    blocked = {'projectmanager_self_audit': {'ok': False, 'detail': 'generation mismatch'}}
    green = {'projectmanager_self_audit': {'ok': True, 'detail': 'GREEN'}}
    record_hold_validation(tmp_path, '32.4.55', blocked, 'ok')
    path = tmp_path / 'Inbox/operating_mode/release_validation_hold.json'
    blocked_bytes = path.read_bytes()

    time.sleep(0.01)
    record_hold_validation(tmp_path, '32.4.55', green, 'ok')
    green_bytes = path.read_bytes()
    green_mtime = path.stat().st_mtime_ns
    assert green_bytes != blocked_bytes

    time.sleep(0.01)
    for _ in range(100):
        record_hold_validation(tmp_path, '32.4.55', green, 'ok')
    assert path.read_bytes() == green_bytes
    assert path.stat().st_mtime_ns == green_mtime
