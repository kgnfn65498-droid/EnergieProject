from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / 'slimmemeterportal_import' / 'rootfs' / 'app' / 'main.py'


def source() -> str:
    return MAIN.read_text(encoding='utf-8')


def test_historical_rebuild_uses_same_native_month_control_as_working_import_button():
    s = source()
    assert '<form id="historical-report-rebuild-form" method="post" action="rebuild-historical-report"><input type="month" name="month" value="{esc(default_month)}" required>' in s
    assert 'pattern="[0-9]{4}_' not in s


def test_historical_rebuild_start_does_not_depend_on_javascript_submit_interception():
    s = source()
    assert "historicalReportForm.addEventListener('submit',startHistoricalReportRebuild)" not in s


def test_server_still_normalizes_native_hyphen_month_before_starting_rebuild():
    s = source()
    route_start = s.index('if path.endswith("/rebuild-historical-report") or path == "/rebuild-historical-report":')
    route_end = s.index('if path.endswith("/run-historical-month")', route_start)
    route = s[route_start:route_end]
    assert '.strip().replace("-", "_")' in route
    assert 'render_historical_report_rebuild_progress(' in route
