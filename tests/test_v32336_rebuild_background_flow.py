from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'


def source():
    return MAIN.read_text(encoding='utf-8')


def test_historical_rebuild_runs_in_background_and_has_dedicated_lock():
    s = source()
    assert 'HISTORICAL_REPORT_REBUILD_LOCK = threading.Lock()' in s
    assert 'def start_historical_report_rebuild_background(' in s
    assert 'threading.Thread(target=worker, daemon=True, name=f"historical-report-{month_key}")' in s


def test_report_status_exposes_historical_rebuild_state():
    s = source()
    assert '"historical_rebuild": {' in s
    assert 'historical_report_rebuild_last_status' in s
    assert 'historical_report_rebuild_last_started' in s
    assert 'historical_report_rebuild_last_finished' in s


def test_console_uses_async_historical_rebuild_polling():
    s = source()
    assert 'id="historical-report-rebuild-form"' in s
    assert 'async function startHistoricalReportRebuild' in s
    assert "fetch('report-generation-status'" in s
    assert 'historical-report-rebuild-result?month=' in s
    assert 'setInterval(pollHistoricalReportRebuild' in s


def test_post_route_starts_background_rebuild_instead_of_blocking():
    s = source()
    marker = 'if path.endswith("/rebuild-historical-report") or path == "/rebuild-historical-report":'
    start = s.index(marker)
    end = s.index('if path.endswith("/run-historical-month")', start)
    route = s[start:end]
    assert 'start_historical_report_rebuild_background(selected)' in route
    assert 'rebuild_historical_report(selected)' not in route
    assert 'HTTPStatus.ACCEPTED' in route


def test_get_result_route_renders_success_or_failure_with_ingress_return():
    s = source()
    assert '/historical-report-rebuild-result' in s
    assert 'Rapport succesvol herbouwd' in s
    assert 'Rapportherbouw mislukt' in s
    assert 'report_overview_href(self.headers.get("X-Ingress-Path", ""))' in s


def test_final_validation_gate_is_runtime_derived_not_hardcoded_waiting():
    s = source()
    assert 'def v32_final_validation_release_state(' in s
    block_start = s.index('"v32_final_validation_gate": {')
    block_end = s.index('"release_identity_runtime": {', block_start)
    block = s[block_start:block_end]
    assert '"release_state": v32_release_state' in block
    assert '"release_state": "awaiting_home_assistant_validation"' not in block


def _load_main_module():
    import importlib.util
    import sys
    appdir = ROOT / 'slimmemeterportal_import/rootfs/app'
    if str(appdir) not in sys.path:
        sys.path.insert(0, str(appdir))
    spec = importlib.util.spec_from_file_location('energie_main_v32336_test', MAIN)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_background_worker_transitions_running_to_completed_and_rejects_duplicate(monkeypatch):
    import threading
    mod = _load_main_module()
    updates = []
    entered = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(mod, 'historical_month_allowed', lambda month: month)
    monkeypatch.setattr(mod, 'load_state', lambda: {'historical_report_rebuild_last_month': '2026_08'})
    monkeypatch.setattr(mod, 'update_state', lambda **kwargs: updates.append(kwargs))

    def fake_rebuild(month):
        entered.set()
        assert release.wait(2)
        return {'status': 'completed', 'month': month}

    monkeypatch.setattr(mod, 'rebuild_historical_report', fake_rebuild)
    mod.HISTORICAL_REPORT_REBUILD_LOCK = threading.Lock()
    first = mod.start_historical_report_rebuild_background('2026_08')
    assert first['status'] == 'started'
    assert entered.wait(2)
    second = mod.start_historical_report_rebuild_background('2026_08')
    assert second['status'] == 'busy'
    assert any(item.get('historical_report_rebuild_last_status') == 'running' for item in updates)
    release.set()
    for _ in range(100):
        if not mod.HISTORICAL_REPORT_REBUILD_LOCK.locked():
            break
        __import__('time').sleep(0.01)
    assert not mod.HISTORICAL_REPORT_REBUILD_LOCK.locked()
    assert any(item.get('historical_report_rebuild_last_status') == 'completed' for item in updates)
    assert any(item.get('historical_report_rebuild_last_finished') for item in updates)


def test_v32_final_validation_release_state_uses_live_release_and_ha(monkeypatch, tmp_path):
    mod = _load_main_module()
    (tmp_path / 'VERSIE.txt').write_text(mod.APP_VERSION, encoding='utf-8')
    monkeypatch.setattr(mod, 'NAS_PROJECT_ROOT', tmp_path)
    monkeypatch.setenv('SUPERVISOR_TOKEN', 'test')
    monkeypatch.setattr(mod, 'home_assistant_states', lambda timeout=3: [{'entity_id': 'sensor.test'}])
    state = mod.v32_final_validation_release_state()
    assert state['release_state'] == 'complete_guarded'
    assert state['release_identity_match'] is True
    assert state['home_assistant_api_reachable'] is True

    (tmp_path / 'VERSIE.txt').write_text('0.0.0', encoding='utf-8')
    state = mod.v32_final_validation_release_state()
    assert state['release_state'] == 'blocked'
