from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CP_SOURCE = ROOT / 'tools/control_plane/control_plane.py'
BOOT_SOURCE = ROOT / 'tools/control_plane/qnap_control_plane_bootstrap.py'
GUARD = ROOT / 'tools/control_plane_runtime_guard.py'


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _copy_control_plane(root: Path) -> Path:
    target = root / 'Data/03_Systeem/Projectmanager/ControlPlane'
    target.mkdir(parents=True)
    (target/'control_plane.py').write_bytes(CP_SOURCE.read_bytes())
    (target/'qnap_control_plane_bootstrap.py').write_bytes(BOOT_SOURCE.read_bytes())
    return target


def test_control_plane_process_writes_loaded_runtime_fingerprint_marker(tmp_path: Path, monkeypatch):
    cp = _load(CP_SOURCE, 'cp55_marker')
    inbox = tmp_path/'Inbox'; inbox.mkdir()
    approved = tmp_path/'approved.json'; approved.write_text('{"schema":1,"items":[]}', encoding='utf-8')
    version = tmp_path/'VERSIE.txt'; version.write_text('32.4.55\n', encoding='utf-8')
    evidence = tmp_path/'evidence'; evidence.mkdir()
    control = cp.ControlPlane(
        inbox=inbox, approved_queue=approved, version_path=version,
        runtime_evidence=evidence, host_project_root='/share/Energie_NAS/EnergieProject', docker=object(),
    )
    control.process_once()
    marker = json.loads((inbox/'control_plane/runtime.json').read_text(encoding='utf-8'))
    assert marker['schema'] == 'energie_control_plane_runtime_v1'
    assert marker['loaded_fingerprint'] == cp.LOADED_RUNTIME_FINGERPRINT
    assert marker['pid'] == os.getpid()
    assert marker['heartbeat_at']


def test_control_plane_guard_rejects_healthy_process_with_stale_loaded_code(tmp_path: Path):
    _copy_control_plane(tmp_path)
    guard = _load(GUARD, 'cp55_guard')
    marker = tmp_path/'Inbox/control_plane/runtime.json'
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        'schema':'energie_control_plane_runtime_v1',
        'loaded_fingerprint':'0'*64,
        'pid':123,
        'heartbeat_at_epoch': time.time(),
    }), encoding='utf-8')

    result = guard.probe(tmp_path, now=time.time(), stale_seconds=30)

    assert result['status'] == 'RESTART_REQUIRED'
    assert result['ready'] is False
    assert result['reason'] == 'loaded_runtime_fingerprint_mismatch'


def test_control_plane_guard_accepts_exact_loaded_fingerprint_and_fresh_heartbeat(tmp_path: Path):
    _copy_control_plane(tmp_path)
    guard = _load(GUARD, 'cp55_guard_green')
    expected = guard.expected_fingerprint(tmp_path)
    marker = tmp_path/'Inbox/control_plane/runtime.json'
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        'schema':'energie_control_plane_runtime_v1',
        'loaded_fingerprint':expected,
        'pid':123,
        'heartbeat_at_epoch': 1000.0,
    }), encoding='utf-8')

    result = guard.probe(tmp_path, now=1010.0, stale_seconds=30)

    assert result['status'] == 'GREEN'
    assert result['ready'] is True
    assert result['expected_fingerprint'] == result['loaded_fingerprint'] == expected


def test_control_plane_guard_fails_closed_when_marker_missing_or_stale(tmp_path: Path):
    _copy_control_plane(tmp_path)
    guard = _load(GUARD, 'cp55_guard_missing')
    missing = guard.probe(tmp_path, now=1000.0, stale_seconds=30)
    assert missing['status'] == 'RESTART_REQUIRED'
    assert missing['reason'] == 'runtime_marker_missing'

    marker = tmp_path/'Inbox/control_plane/runtime.json'
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        'schema':'energie_control_plane_runtime_v1',
        'loaded_fingerprint':guard.expected_fingerprint(tmp_path),
        'pid':123,
        'heartbeat_at_epoch': 900.0,
    }), encoding='utf-8')
    stale = guard.probe(tmp_path, now=1000.0, stale_seconds=30)
    assert stale['status'] == 'RESTART_REQUIRED'
    assert stale['reason'] == 'runtime_heartbeat_stale'
