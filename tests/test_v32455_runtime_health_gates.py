from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))

import energy_health_collector as health


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _fingerprint(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for name, data in files:
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(data)
    return digest.hexdigest()


def test_control_plane_health_detects_stale_loaded_runtime_even_with_fresh_marker(tmp_path: Path):
    cp = tmp_path/'Data/03_Systeem/Projectmanager/ControlPlane'; cp.mkdir(parents=True)
    files = [('control_plane.py', b'new cp'), ('qnap_control_plane_bootstrap.py', b'new boot')]
    for name, data in files: (cp/name).write_bytes(data)
    _write_json(tmp_path/'Inbox/control_plane/runtime.json', {
        'schema':'energie_control_plane_runtime_v1',
        'loaded_fingerprint':'0'*64,
        'heartbeat_at_epoch':1000.0,
    })
    result = health._control_plane_runtime_check(tmp_path, now=datetime.fromtimestamp(1010, timezone.utc))
    assert result['status'] == 'RED'
    assert result['reason'] == 'loaded_runtime_fingerprint_mismatch'


def test_control_plane_health_green_requires_exact_loaded_fingerprint(tmp_path: Path):
    cp = tmp_path/'Data/03_Systeem/Projectmanager/ControlPlane'; cp.mkdir(parents=True)
    files = [('control_plane.py', b'cp'), ('qnap_control_plane_bootstrap.py', b'boot')]
    for name, data in files: (cp/name).write_bytes(data)
    expected = _fingerprint(files)
    _write_json(tmp_path/'Inbox/control_plane/runtime.json', {
        'schema':'energie_control_plane_runtime_v1',
        'loaded_fingerprint':expected,
        'heartbeat_at_epoch':1000.0,
    })
    result = health._control_plane_runtime_check(tmp_path, now=datetime.fromtimestamp(1010, timezone.utc))
    assert result['status'] == 'GREEN'
    assert result['details']['expected_fingerprint'] == expected


def test_command_ingress_health_is_red_when_envelope_has_no_receipt(tmp_path: Path):
    ingress = tmp_path/'Data/03_Systeem/Projectmanager/CommandIngress'; ingress.mkdir(parents=True)
    _write_json(ingress/'abc.json', {'schema':'energie_pmv2_command_ingress_v1','id':'abc','command':{'intent':'status'}})
    _write_json(tmp_path/'Inbox/projectmanager_v2/RuntimeV2/commands/ingress_receipts.json', {'schema':1,'items':{}})
    result = health._command_ingress_consumer_check(tmp_path)
    assert result['status'] == 'RED'
    assert result['reason'] == 'unconsumed_envelopes'
    assert result['details']['pending_ids'] == ['abc']


def test_command_ingress_health_green_only_after_receipt_proves_consumption(tmp_path: Path):
    ingress = tmp_path/'Data/03_Systeem/Projectmanager/CommandIngress'; ingress.mkdir(parents=True)
    _write_json(ingress/'abc.json', {'schema':'energie_pmv2_command_ingress_v1','id':'abc','command':{'intent':'status'}})
    _write_json(tmp_path/'Inbox/projectmanager_v2/RuntimeV2/commands/ingress_receipts.json', {
        'schema':1,'items':{'abc':{'status':'IMPORTED','ingress_id':'abc','command_id':'cmd1'}}
    })
    _write_json(tmp_path/'Inbox/projectmanager_v2/RuntimeV2/commands/queue.json', {
        'schema':1,'items':[{'id':'cmd1','ingress_id':'abc','intent':'status','status':'PENDING'}]
    })
    result = health._command_ingress_consumer_check(tmp_path)
    assert result['status'] == 'GREEN'
    assert result['reason'] == 'all_current_envelopes_proven_consumed'
    assert result['details']['pending_count'] == 0
    assert result['details']['receipted_current_count'] == 1
    assert result['details']['queued_import_count'] == 1


def test_command_ingress_health_rejects_import_receipt_without_actual_queued_command(tmp_path: Path):
    ingress = tmp_path/'Data/03_Systeem/Projectmanager/CommandIngress'; ingress.mkdir(parents=True)
    _write_json(ingress/'abc.json', {'schema':'energie_pmv2_command_ingress_v1','id':'abc','command':{'intent':'status'}})
    _write_json(tmp_path/'Inbox/projectmanager_v2/RuntimeV2/commands/ingress_receipts.json', {
        'schema':1,'items':{'abc':{'status':'IMPORTED','ingress_id':'abc','command_id':'missing-command'}}
    })
    _write_json(tmp_path/'Inbox/projectmanager_v2/RuntimeV2/commands/queue.json', {'schema':1,'items':[]})

    result = health._command_ingress_consumer_check(tmp_path)

    assert result['status'] == 'RED'
    assert result['reason'] == 'receipt_without_queued_command'
    assert result['details']['orphan_receipt_ids'] == ['abc']


def test_command_ingress_health_green_after_real_consumer_imports_to_queue(tmp_path: Path):
    from command_ingress import CommandIngressConsumer
    from command_store import CommandStore

    ingress = tmp_path/'Data/03_Systeem/Projectmanager/CommandIngress'; ingress.mkdir(parents=True)
    _write_json(ingress/'abc.json', {'schema':'energie_pmv2_command_ingress_v1','id':'abc','command':{'intent':'status'}})
    runtime = tmp_path/'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime/'commands/queue.json')
    consumer = CommandIngressConsumer(ingress, runtime/'commands/ingress_receipts.json', commands)

    consumed = consumer.consume(max_items=20)
    result = health._command_ingress_consumer_check(tmp_path)

    assert len(consumed) == 1 and consumed[0]['status'] == 'IMPORTED'
    assert result['status'] == 'GREEN'
    assert result['reason'] == 'all_current_envelopes_proven_consumed'
    assert result['details']['queued_import_count'] == 1


def test_empty_command_ingress_scan_creates_consumer_receipt_ledger_once(tmp_path: Path):
    from command_ingress import CommandIngressConsumer
    from command_store import CommandStore

    ingress = tmp_path/'Data/03_Systeem/Projectmanager/CommandIngress'; ingress.mkdir(parents=True)
    runtime = tmp_path/'Inbox/projectmanager_v2/RuntimeV2'
    receipts = runtime/'commands/ingress_receipts.json'
    consumer = CommandIngressConsumer(ingress, receipts, CommandStore(runtime/'commands/queue.json'))

    assert not receipts.exists()
    assert consumer.consume(max_items=20) == []
    first = receipts.read_bytes()
    first_mtime = receipts.stat().st_mtime_ns
    assert consumer.consume(max_items=20) == []

    assert receipts.read_bytes() == first
    assert receipts.stat().st_mtime_ns == first_mtime
    result = health._command_ingress_consumer_check(tmp_path)
    assert result['status'] == 'GREEN'
    assert result['details']['pending_count'] == 0
