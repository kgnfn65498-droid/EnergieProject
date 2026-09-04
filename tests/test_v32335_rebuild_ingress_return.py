from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'


def rebuild_success_route_source() -> str:
    source = MAIN.read_text(encoding='utf-8')
    start = source.index('elif path.endswith("/historical-report-rebuild-result")')
    end = source.index('elif path.endswith("/reports")', start)
    return source[start:end]


def test_rebuild_success_return_uses_home_assistant_ingress_root():
    route = rebuild_success_route_source()
    assert 'X-Ingress-Path' in route
    assert 'report_overview_href' in route
    assert "href='./'" not in route


def test_v32335_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.0'
    assert 'version: "32.4.0"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.0"' in MAIN.read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.0"' in (ROOT / 'slimmemeterportal_import/rootfs/app/mode_entrypoint.py').read_text(encoding='utf-8')
