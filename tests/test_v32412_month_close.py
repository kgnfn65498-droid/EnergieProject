import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'


def load_main(name):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _complete_report_state(pdf, recovery):
    return {
        'last_central_validation': {'status': 'error', 'errors': ['stale']},
        'report_runtime_last_status': 'ok',
        'report_runtime_modules': ['reportlab'],
        'report_generators_install_status': 'completed',
        'report_service_generators': ['page_1', 'page_2', 'pages_3_13'],
        'report_adapter_last_status': 'completed',
        'report_adapter_last_files': ['adapter.json'],
        'report_merge_last_status': 'completed',
        'report_merge_last_output': str(pdf),
        'report_output_last_status': 'completed',
        'report_output_last_files': [str(pdf), str(recovery)],
    }


def test_report_handoff_keeps_month_input_validation_separate_from_pre_report_validation(tmp_path):
    m = load_main('v32412_handoff_provenance')
    month_input = {'status': 'completed_info', 'month': '2026_08'}
    pre_report = {'status': 'warning', 'month': '2026_08', 'errors': [], 'warnings': ['historical info']}
    m.update_state = lambda **kwargs: None

    result = m.create_report_handoff(
        2026, 8, '/input/2026_08', str(tmp_path), None,
        pre_report, month_input_validation=month_input,
    )

    request = result['request_payload']
    assert request['pre_report_validation'] == pre_report
    assert request['pre_report_validation_status'] == 'warning'
    assert request['month_input_validation'] == month_input
    assert request['month_input_validation_status'] == 'completed_info'
    assert request['central_validation'] == pre_report  # compatibility alias, never month-input provenance


def test_historical_report_audit_accepts_current_pre_report_warning_not_month_input_completed_info(monkeypatch, tmp_path):
    m = load_main('v32412_historical_report_rootcause')
    month = '2026_08'
    input_folder = tmp_path / 'input' / month
    input_folder.mkdir(parents=True)
    output = tmp_path / 'output' / month
    output.mkdir(parents=True)
    pdf = output / f'Energierapport_{month}.pdf'
    recovery = output / f'Recovery_Update_{month}.zip'
    pdf.write_bytes(b'%PDF-v32412')
    recovery.write_bytes(b'PK-v32412')
    state = _complete_report_state(pdf, recovery)

    monkeypatch.setattr(m, 'load_state', lambda: state)
    monkeypatch.setattr(m, 'update_state', lambda **kwargs: state.update(kwargs))
    monkeypatch.setattr(m, 'validate_report_input_files', lambda *args, **kwargs: {'status': 'ok'})
    monkeypatch.setattr(m, 'validate_report_handoff_files', lambda handoff: {'status': 'ok', 'errors': []})
    monkeypatch.setattr(m, 'execute_local_report_service', lambda *args, **kwargs: {'status': 'completed', 'error': None})
    monkeypatch.setattr(m, 'cleanup_report_service_history', lambda options: {'status': 'completed'})
    monkeypatch.setattr(m, 'build_compact_workflow_summary', lambda month_key: {'status': 'completed', 'month': month_key})
    handoff = {
        'month': month,
        'input_folder': str(input_folder),
        'month_input_validation': {'status': 'completed_info', 'month': month},
        'central_validation': {'status': 'completed_info', 'month': month},  # legacy bad provenance
        'pre_report_validation': {'status': 'warning', 'month': month, 'errors': [], 'warnings': ['historical info']},
    }
    monkeypatch.setattr(m, 'load_report_handoff', lambda path: dict(handoff))

    result = m.run_report_generation_from_handoff(
        SimpleNamespace(report_service_enabled=True, report_trigger_enabled=False),
        tmp_path / 'report_request.json',
    )

    assert result['status'] == 'completed'
    central = next(item for item in result['audit']['checks'] if item['name'] == 'central_validation')
    assert central['status'] == 'ok'
    assert central['detail']['status'] == 'warning'


def test_full_workflow_passes_pre_report_validation_into_transfer_handoff():
    source = MAIN.read_text(encoding='utf-8')
    workflow = source.split('def run_full_month_workflow(', 1)[1].split('\ndef ', 1)[0]
    assert 'create_transfer_package(' in workflow
    assert 'report_validation=pre_report_validation' in workflow


def test_identical_automatic_failure_notification_is_suppressed_inside_cooldown_but_changed_error_is_immediate(monkeypatch):
    m = load_main('v32412_failure_dedupe')
    state = {}
    monkeypatch.setattr(m, 'load_state', lambda: dict(state))
    monkeypatch.setattr(m, 'update_state', lambda **kwargs: state.update(kwargs))
    now = datetime(2026, 9, 8, 10, 0, tzinfo=m.TZ)

    first = m.automatic_failure_notification_decision(
        '2026_08', 'Rapportgenerator koppelen', ['rapport niet voltooid'], now=now, cooldown_hours=24,
    )
    repeated = m.automatic_failure_notification_decision(
        '2026_08', 'Rapportgenerator koppelen', ['rapport niet voltooid'], now=now + timedelta(hours=6), cooldown_hours=24,
    )
    changed = m.automatic_failure_notification_decision(
        '2026_08', 'Rapportgenerator koppelen', ['nieuwe echte fout'], now=now + timedelta(hours=7), cooldown_hours=24,
    )

    assert first['notify'] is True
    assert repeated['notify'] is False
    assert repeated['suppressed_count'] == 1
    assert changed['notify'] is True
    assert changed['fingerprint'] != first['fingerprint']


def test_identical_automatic_failure_is_reminded_after_cooldown_and_success_reset_allows_future_alert(monkeypatch):
    m = load_main('v32412_failure_reminder')
    state = {}
    monkeypatch.setattr(m, 'load_state', lambda: dict(state))
    monkeypatch.setattr(m, 'update_state', lambda **kwargs: state.update(kwargs))
    now = datetime(2026, 9, 8, 10, 0, tzinfo=m.TZ)
    args = ('2026_08', 'Rapportgenerator koppelen', ['rapport niet voltooid'])

    first = m.automatic_failure_notification_decision(*args, now=now, cooldown_hours=24)
    reminder = m.automatic_failure_notification_decision(*args, now=now + timedelta(hours=25), cooldown_hours=24)
    m.reset_automatic_failure_notification_state('2026_08')
    after_recovery = m.automatic_failure_notification_decision(*args, now=now + timedelta(hours=26), cooldown_hours=24)

    assert first['notify'] is True
    assert reminder['notify'] is True
    assert after_recovery['notify'] is True


def test_representative_full_month_workflow_completes_through_report_generator(monkeypatch, tmp_path):
    m = load_main('v32412_full_month_e2e')
    state = {}
    options = SimpleNamespace(
        full_workflow_enabled=True,
        workflow_notify_home_assistant=False,
        workflow_notify_on_start=False,
        workflow_step_timeout_seconds=900,
        full_workflow_stop_on_error=True,
        full_workflow_run_epex_when_enabled=False,
        enphase_enabled=False,
        epex_electricity_enabled=False,
        epex_gas_enabled=False,
        report_service_enabled=True,
        report_trigger_enabled=False,
        automatic_month_close_retry_hours=6,
    )
    monkeypatch.setattr(m.Options, 'load', classmethod(lambda cls: options))
    monkeypatch.setattr(m, 'load_state', lambda: dict(state))
    monkeypatch.setattr(m, 'update_state', lambda **kwargs: state.update(kwargs))
    monkeypatch.setattr(m, 'set_workflow_lock_state', lambda **kwargs: state.update({'workflow_lock_status': kwargs.get('status')}))
    monkeypatch.setattr(m, 'update_workflow_lock_step', lambda *args, **kwargs: None)
    monkeypatch.setattr(m, 'append_workflow_log', lambda *args, **kwargs: None)
    monkeypatch.setattr(m, 'append_finalization_debug', lambda *args, **kwargs: None)
    monkeypatch.setattr(m, 'append_audit_event', lambda *args, **kwargs: None)
    monkeypatch.setattr(m, 'persist_normalized_status', lambda *args, **kwargs: None)
    monkeypatch.setattr(m, 'workflow_result_dir', lambda month: tmp_path / 'results' / month)
    monkeypatch.setattr(m, 'previous_workflow_result', lambda month: {})
    monkeypatch.setattr(m, 'test_api', lambda: {'status': 'ok'})
    monkeypatch.setattr(m, 'coordinated_month_import', lambda *args, **kwargs: {'status': 'completed'})
    monkeypatch.setattr(m, 'discover_homewizard_devices', lambda *args, **kwargs: {'status': 'completed_info'})
    monkeypatch.setattr(m, 'build_month_input', lambda *args, **kwargs: {'status': 'completed_info', 'missing_required': [], 'empty_required': []})
    pre_report = {'status': 'warning', 'month': '2026_08', 'errors': [], 'warnings': ['historical info']}
    monkeypatch.setattr(m, 'validate_pre_report_workflow', lambda *args, **kwargs: dict(pre_report))

    captured = {}
    def transfer(month_key, *, replace_existing, send_notification, report_validation):
        captured['report_validation'] = report_validation
        return {'status': 'completed', 'report_handoff': {'request': str(tmp_path / 'request.json')}}
    monkeypatch.setattr(m, 'create_transfer_package', transfer)
    monkeypatch.setattr(m, 'report_input_readiness', lambda *args, **kwargs: {'status': 'ready', 'missing': [], 'empty': []})
    monkeypatch.setattr(m, 'run_report_generation_from_handoff', lambda *args, **kwargs: {'status': 'completed', 'audit': {'status': 'completed'}})
    monkeypatch.setattr(m, 'create_project_backup', lambda *args, **kwargs: {'status': 'completed'})
    monkeypatch.setattr(m, 'run_historical_energy_excel_sidecar', lambda *args, **kwargs: {'status': 'completed'})

    result = m.run_full_month_workflow('2026_08', collect_live_snapshots=False, trigger='automatic_test')

    assert captured['report_validation'] == pre_report
    assert result['status'] in {'completed', 'completed_warning'}
    assert result['failed_step'] is None
    assert result['errors'] == []
    report_step = next(step for step in result['steps'] if step['name'] == 'Rapportgenerator koppelen')
    assert report_step['status'] == 'ok'
    assert result['all_steps_completed'] is True
