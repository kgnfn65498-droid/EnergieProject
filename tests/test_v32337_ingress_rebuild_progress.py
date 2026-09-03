import importlib.util
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'
APPDIR = MAIN.parent


def load_main():
    if str(APPDIR) not in sys.path:
        sys.path.insert(0, str(APPDIR))
    spec = importlib.util.spec_from_file_location('energie_main_v32337_test', MAIN)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_browser_post_returns_html_progress_page_instead_of_raw_json(monkeypatch):
    mod = load_main()
    monkeypatch.setattr(
        mod,
        'start_historical_report_rebuild_background',
        lambda month: {'status': 'started', 'month': month, 'started_at': '2026-09-03T22:55:00+02:00'},
    )

    handler = object.__new__(mod.Handler)
    payload = b'month=2026-08'
    handler.path = '/2ea5628f_slimmemeterportal_import/rebuild-historical-report'
    handler.headers = {
        'Content-Length': str(len(payload)),
        'X-Ingress-Path': '/2ea5628f_slimmemeterportal_import',
        'Accept': 'text/html,application/xhtml+xml',
    }
    handler.rfile = io.BytesIO(payload)
    captured = {}
    handler.send_body = lambda status, body, content_type, *args, **kwargs: captured.update(
        status=status, body=body, content_type=content_type
    )

    handler.do_POST()

    assert captured['status'] == 202
    assert captured['content_type'] == 'text/html; charset=utf-8'
    html = captured['body'].decode('utf-8')
    assert 'Rapport wordt gemaakt' in html
    assert 'report-generation-status' in html
    assert 'historical-report-rebuild-result?month=2026-08' in html
    assert 'setInterval' in html
    assert '{"status": "started"' not in html


def test_progress_page_uses_ingress_relative_navigation(monkeypatch):
    mod = load_main()
    monkeypatch.setattr(
        mod,
        'start_historical_report_rebuild_background',
        lambda month: {'status': 'started', 'month': month},
    )
    handler = object.__new__(mod.Handler)
    payload = b'month=2026-08'
    handler.path = '/2ea5628f_slimmemeterportal_import/rebuild-historical-report'
    handler.headers = {
        'Content-Length': str(len(payload)),
        'X-Ingress-Path': '/2ea5628f_slimmemeterportal_import',
        'Accept': 'text/html',
    }
    handler.rfile = io.BytesIO(payload)
    captured = {}
    handler.send_body = lambda status, body, content_type, *args, **kwargs: captured.update(
        status=status, body=body, content_type=content_type
    )

    handler.do_POST()
    html = captured['body'].decode('utf-8')

    assert "fetch('report-generation-status'" in html
    assert "window.location.href='historical-report-rebuild-result?month=2026-08'" in html
    assert 'Terug naar operationele console' in html
