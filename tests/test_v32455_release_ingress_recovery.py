from __future__ import annotations

import importlib.util
import io
import json
import os
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools' / 'release_ingress_recovery.py'


def _load_helper():
    spec = importlib.util.spec_from_file_location('release_ingress_recovery', HELPER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _tree(root: Path):
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/failed','Inbox/logs'):
        (root / rel).mkdir(parents=True, exist_ok=True)


def _age(path: Path, seconds: int):
    then = time.time() - seconds
    os.utime(path, (then, then))


def _valid_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('VERSIE.txt', '32.4.55\n')
        zf.writestr('README.md', 'ok\n')
    return buffer.getvalue()


def test_identical_duplicate_incoming_converges_to_one_and_quarantines_extra(tmp_path: Path):
    _tree(tmp_path)
    a = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55.zip'
    b = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55-copy.zip'
    payload = _valid_zip_bytes()
    a.write_bytes(payload)
    b.write_bytes(payload)
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    remaining = sorted((tmp_path/'Inbox/incoming').glob('*.zip'))
    dupes = sorted((tmp_path/'Inbox/failed/duplicates').glob('*.zip'))
    assert result['status'] == 'RECOVERED'
    assert result['action'] == 'DEDUPLICATED_INCOMING'
    assert len(remaining) == 1
    assert len(dupes) == 1
    assert remaining[0].read_bytes() == payload
    assert dupes[0].read_bytes() == payload


def test_different_incoming_contents_fail_closed_without_mutation(tmp_path: Path):
    _tree(tmp_path)
    a = tmp_path/'Inbox/incoming/A.zip'; a.write_bytes(b'a')
    b = tmp_path/'Inbox/incoming/B.zip'; b.write_bytes(b'b')
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'multiple_distinct_incoming'
    assert sorted(p.name for p in (tmp_path/'Inbox/incoming').glob('*.zip')) == ['A.zip','B.zip']
    assert not list((tmp_path/'Inbox/failed').rglob('*.zip'))


def test_orphan_processing_returns_to_incoming_when_no_installer_lock(tmp_path: Path):
    _tree(tmp_path)
    p = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'
    p.write_bytes(b'candidate')
    _age(p, 120)
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'RECOVERED'
    assert result['action'] == 'REQUEUED_ORPHAN_PROCESSING'
    assert not p.exists()
    assert (tmp_path/'Inbox/incoming'/p.name).read_bytes() == b'candidate'


def test_fresh_installer_lock_preserves_processing(tmp_path: Path):
    _tree(tmp_path)
    p = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'; p.write_bytes(b'candidate'); _age(p, 120)
    lock = tmp_path/'Inbox/.installer.lock'; lock.mkdir()
    hb = lock/'heartbeat'; hb.write_text(str(int(time.time())), encoding='utf-8')
    (lock/'owner.json').write_text(json.dumps({'pid':123,'started_at_epoch':int(time.time())}), encoding='utf-8')
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'WAITING'
    assert result['reason'] == 'installer_lock_fresh'
    assert p.exists() and lock.exists()


def test_stale_installer_lock_and_orphan_processing_recover_together(tmp_path: Path):
    _tree(tmp_path)
    p = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'; p.write_bytes(b'candidate'); _age(p, 120)
    lock = tmp_path/'Inbox/.installer.lock'; lock.mkdir()
    hb = lock/'heartbeat'; hb.write_text(str(int(time.time())-120), encoding='utf-8'); _age(hb,120)
    (lock/'owner.json').write_text(json.dumps({'pid':99999999,'started_at_epoch':int(time.time())-120}), encoding='utf-8')
    _age(lock,120)
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'RECOVERED'
    assert result['action'] == 'RECOVERED_STALE_LOCK_AND_PROCESSING'
    assert not lock.exists()
    assert (tmp_path/'Inbox/incoming'/p.name).exists()


def test_stale_lock_without_processing_is_removed(tmp_path: Path):
    _tree(tmp_path)
    lock = tmp_path/'Inbox/.installer.lock'; lock.mkdir()
    hb = lock/'heartbeat'; hb.write_text(str(int(time.time())-120), encoding='utf-8'); _age(hb,120); _age(lock,120)
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'RECOVERED'
    assert result['action'] == 'REMOVED_STALE_INSTALLER_LOCK'
    assert not lock.exists()


def test_reconcile_is_idempotent_after_orphan_requeue(tmp_path: Path):
    _tree(tmp_path)
    p = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'; p.write_bytes(b'candidate'); _age(p, 120)
    mod = _load_helper()
    first = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())
    second = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())
    assert first['status'] == 'RECOVERED'
    assert second['status'] in {'READY','WAITING'}
    assert len(list((tmp_path/'Inbox/incoming').glob('*.zip'))) == 1


def test_quarantine_corrupt_moves_only_named_incoming_file(tmp_path: Path):
    _tree(tmp_path)
    bad = tmp_path/'Inbox/incoming/bad.zip'; bad.write_bytes(b'notzip'); _age(bad, 120)
    mod = _load_helper()
    result = mod.quarantine_corrupt(tmp_path, bad.name, stale_seconds=60, now=time.time())
    assert result['status'] == 'RECOVERED'
    assert result['action'] == 'QUARANTINED_CORRUPT'
    assert not bad.exists()
    quarantined = list((tmp_path/'Inbox/failed/corrupt').glob('*.zip'))
    assert len(quarantined) == 1 and quarantined[0].read_bytes() == b'notzip'


def test_release_scripts_reference_v55_recovery_contract():
    watcher = (ROOT/'tests/fixtures/pre57/release_watcher.sh').read_text(encoding='utf-8')
    installer = (ROOT/'tests/fixtures/pre57/release_installer.sh').read_text(encoding='utf-8')
    assert 'release_ingress_recovery.py' in watcher
    assert 'reconcile --root "$ROOT"' in watcher
    assert 'quarantine-corrupt --root "$ROOT"' in watcher
    assert 'INSTALLER_LOCK_HEARTBEAT' in installer
    assert 'refresh_installer_lock_heartbeat' in installer


def test_idle_reconcile_100_cycles_does_not_spin_evidence_file(tmp_path: Path):
    _tree(tmp_path)
    mod = _load_helper()
    first = mod.reconcile(tmp_path, stale_seconds=60, now=1_000.0)
    evidence = tmp_path/'Inbox/logs/release_ingress_recovery.json'
    assert first['status'] == 'WAITING'
    before = evidence.read_bytes()
    before_stat = evidence.stat().st_mtime_ns
    for index in range(1, 101):
        result = mod.reconcile(tmp_path, stale_seconds=60, now=1_000.0 + index)
        assert result['status'] == 'WAITING'
    assert evidence.read_bytes() == before
    assert evidence.stat().st_mtime_ns == before_stat


def test_live_installer_owner_pid_prevents_stale_lock_recovery(tmp_path: Path):
    _tree(tmp_path)
    p = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'
    p.write_bytes(b'candidate')
    _age(p, 120)
    lock = tmp_path/'Inbox/.installer.lock'; lock.mkdir()
    hb = lock/'heartbeat'; hb.write_text(str(int(time.time())-120), encoding='utf-8'); _age(hb,120)
    (lock/'owner.json').write_text(json.dumps({'pid':os.getpid(),'started_at_epoch':int(time.time())-120}), encoding='utf-8')
    _age(lock,120)
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'WAITING'
    assert result['reason'] == 'installer_owner_alive'
    assert p.exists() and lock.exists()


def test_duplicate_recovery_survives_helper_restart_without_second_side_effect(tmp_path: Path):
    _tree(tmp_path)
    a = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55.zip'
    b = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55-copy.zip'
    payload = _valid_zip_bytes()
    a.write_bytes(payload)
    b.write_bytes(payload)
    first_mod = _load_helper()
    first = first_mod.reconcile(tmp_path, stale_seconds=60, now=1_000.0)
    assert first['action'] == 'DEDUPLICATED_INCOMING'
    quarantined_before = sorted(p.relative_to(tmp_path).as_posix() for p in (tmp_path/'Inbox/failed').rglob('*.zip'))

    second_mod = _load_helper()  # fresh module load models watcher/helper restart
    second = second_mod.reconcile(tmp_path, stale_seconds=60, now=1_100.0)

    assert second['status'] == 'READY'
    assert len(list((tmp_path/'Inbox/incoming').glob('*.zip'))) == 1
    assert sorted(p.relative_to(tmp_path).as_posix() for p in (tmp_path/'Inbox/failed').rglob('*.zip')) == quarantined_before


def test_orphan_requeue_survives_helper_restart_without_duplicate_claim(tmp_path: Path):
    _tree(tmp_path)
    item = tmp_path/'Inbox/processing/EnergieProject_v32.4.55.zip'
    item.write_bytes(b'candidate')
    _age(item, 120)
    first_mod = _load_helper()
    first = first_mod.reconcile(tmp_path, stale_seconds=60, now=time.time())
    assert first['action'] == 'REQUEUED_ORPHAN_PROCESSING'

    second_mod = _load_helper()
    second = second_mod.reconcile(tmp_path, stale_seconds=60, now=time.time()+120)

    assert second['status'] == 'READY'
    assert not list((tmp_path/'Inbox/processing').glob('*.zip'))
    assert [p.name for p in (tmp_path/'Inbox/incoming').glob('*.zip')] == ['EnergieProject_v32.4.55.zip']


def test_distinct_incoming_conflict_is_stable_for_100_cycles(tmp_path: Path):
    _tree(tmp_path)
    a = tmp_path/'Inbox/incoming/A.zip'; a.write_bytes(b'a')
    b = tmp_path/'Inbox/incoming/B.zip'; b.write_bytes(b'b')
    mod = _load_helper()
    first = mod.reconcile(tmp_path, stale_seconds=60, now=1_000.0)
    evidence = tmp_path/'Inbox/logs/release_ingress_recovery.json'
    before_evidence = evidence.read_bytes()
    before_mtime = evidence.stat().st_mtime_ns
    before_files = {p.name: p.read_bytes() for p in (tmp_path/'Inbox/incoming').glob('*.zip')}

    for cycle in range(1, 101):
        result = mod.reconcile(tmp_path, stale_seconds=60, now=1_000.0+cycle)
        assert result['status'] == 'BLOCKED'
        assert result['reason'] == 'multiple_distinct_incoming'

    assert evidence.read_bytes() == before_evidence
    assert evidence.stat().st_mtime_ns == before_mtime
    assert {p.name: p.read_bytes() for p in (tmp_path/'Inbox/incoming').glob('*.zip')} == before_files
    assert not list((tmp_path/'Inbox/failed').rglob('*.zip'))


def test_installer_never_performs_independent_orphan_processing_recovery(tmp_path: Path):
    import subprocess
    root = tmp_path / 'energy'
    (root / 'App').mkdir(parents=True)
    processing = root / 'Inbox/processing'
    processing.mkdir(parents=True)
    orphan = processing / 'EnergieProject_v32.4.55.zip'
    orphan.write_bytes(b'orphan')
    _age(orphan, 120)
    env = os.environ.copy()
    env['ENERGIE_ROOT'] = str(root)
    env['ENERGIE_INSTALLER_REEXEC'] = '1'
    env['ENERGIE_PROCESSING_STALE_SECONDS'] = '30'

    result = subprocess.run(
        ['sh', str(ROOT / 'tests/fixtures/pre57/release_installer.sh')],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert orphan.exists(), 'installer must leave Processing untouched for canonical watcher recovery'
    assert not (root / 'Inbox/failed' / orphan.name).exists()
    assert 'processing' in (result.stdout + result.stderr).lower()


def test_watcher_once_runs_canonical_recovery_before_installer(tmp_path: Path):
    import subprocess
    root = tmp_path / 'energy'
    app_tools = root / 'App/tools'
    app_tools.mkdir(parents=True)
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/failed', 'Inbox/logs'):
        (root / rel).mkdir(parents=True, exist_ok=True)

    # The watcher uses its installed helper and installer. Keep the installer a
    # tiny observer so this test exercises watcher -> recovery -> installer order
    # without performing a release deployment.
    (app_tools / 'release_ingress_recovery.py').write_bytes((ROOT / 'tools/release_ingress_recovery.py').read_bytes())
    preflight = app_tools / 'release_preflight.py'
    preflight.write_text(
        '#!/usr/bin/env python3\n'
        'from pathlib import Path\n'
        'import argparse, sys\n'
        'p=argparse.ArgumentParser(); p.add_argument("--root"); p.add_argument("--candidate"); a=p.parse_args()\n'
        'root=Path(a.root); candidate=Path(a.candidate)\n'
        'ok=candidate.is_file() and not list((root/"Inbox/processing").glob("*.zip"))\n'
        'raise SystemExit(0 if ok else 3)\n',
        encoding='utf-8',
    )
    preflight.chmod(0o755)
    installer = app_tools / 'release_installer.sh'
    installer.write_text(
        '#!/bin/sh\nset -eu\n'
        'test -f "$ENERGIE_ROOT/Inbox/incoming/EnergieProject_v32.4.55.zip"\n'
        'test ! -e "$ENERGIE_ROOT/Inbox/processing/EnergieProject_v32.4.55.zip"\n'
        'printf recovered > "$ENERGIE_ROOT/Inbox/logs/once-installer-marker"\n',
        encoding='utf-8',
    )
    installer.chmod(0o755)

    orphan = root / 'Inbox/processing/EnergieProject_v32.4.55.zip'
    orphan.write_bytes(b'candidate')
    _age(orphan, 120)
    env = os.environ.copy()
    env['ENERGIE_ROOT'] = str(root)
    env['ENERGIE_INGRESS_RECOVERY_STALE_SECONDS'] = '30'
    env['ENERGIE_WATCHER_REEXEC'] = '1'

    result = subprocess.run(
        ['sh', str(ROOT / 'tests/fixtures/pre57/release_watcher.sh'), 'once'],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / 'Inbox/logs/once-installer-marker').read_text() == 'recovered'
    assert not orphan.exists()


def test_identical_nonintegral_duplicates_wait_without_deduplication(tmp_path: Path):
    _tree(tmp_path)
    a = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55.zip'
    b = tmp_path/'Inbox/incoming/EnergieProject_v32.4.55-copy.zip'
    a.write_bytes(b'partial-zip-bytes')
    b.write_bytes(b'partial-zip-bytes')
    mod = _load_helper()

    result = mod.reconcile(tmp_path, stale_seconds=60, now=time.time())

    assert result['status'] == 'WAITING'
    assert result['reason'] == 'identical_incoming_not_integral'
    assert sorted(p.name for p in (tmp_path/'Inbox/incoming').glob('*.zip')) == sorted([a.name, b.name])
    assert not list((tmp_path/'Inbox/failed').rglob('*.zip'))


def test_young_corrupt_candidate_waits_without_evidence_spin(tmp_path: Path):
    _tree(tmp_path)
    bad = tmp_path/'Inbox/incoming/bad.zip'
    bad.write_bytes(b'not-a-complete-zip')
    os.utime(bad, (1_000.0, 1_000.0))
    mod = _load_helper()

    first = mod.quarantine_corrupt(tmp_path, bad.name, stale_seconds=60, now=1_010.0)
    evidence = tmp_path/'Inbox/logs/release_ingress_recovery.json'
    before = evidence.read_bytes()
    before_mtime = evidence.stat().st_mtime_ns
    for cycle in range(1, 21):
        result = mod.quarantine_corrupt(tmp_path, bad.name, stale_seconds=60, now=1_010.0 + cycle)
        assert result['status'] == 'WAITING'
        assert result['reason'] == 'corrupt_candidate_not_stale'
    assert bad.is_file()
    assert not list((tmp_path/'Inbox/failed/corrupt').glob('*.zip'))
    assert evidence.read_bytes() == before
    assert evidence.stat().st_mtime_ns == before_mtime
