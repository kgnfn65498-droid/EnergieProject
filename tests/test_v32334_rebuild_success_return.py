from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'


def rebuild_success_route_source() -> str:
    source = MAIN.read_text(encoding='utf-8')
    start = source.index('elif path.endswith("/historical-report-rebuild-result")')
    end = source.index('elif path.endswith("/reports")', start)
    return source[start:end]


def test_rebuild_success_has_explicit_return_button_and_no_auto_refresh():
    route = rebuild_success_route_source()
    assert 'Rapport succesvol herbouwd' in route
    assert 'Terug naar operationele console' in route
    assert "class='return-button'" in route
    assert 'report_overview_href' in route
    assert 'X-Ingress-Path' in route
    assert "meta http-equiv='refresh'" not in route


def test_v32334_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.4'
    assert 'version: "32.4.4"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.4"' in MAIN.read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.4"' in (ROOT / 'slimmemeterportal_import/rootfs/app/mode_entrypoint.py').read_text(encoding='utf-8')
