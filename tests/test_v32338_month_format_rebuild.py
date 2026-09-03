import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'
APPDIR = MAIN.parent


def load_main():
    if str(APPDIR) not in sys.path:
        sys.path.insert(0, str(APPDIR))
    spec = importlib.util.spec_from_file_location('energie_main_v32338_test', MAIN)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parse_month_key_accepts_browser_hyphen_and_canonical_underscore():
    mod = load_main()
    assert mod.parse_month_key('2026_08') == (2026, 8)
    assert mod.parse_month_key('2026-08') == (2026, 8)


def test_historical_rebuild_form_uses_canonical_yyyy_mm_text_value():
    source = MAIN.read_text(encoding='utf-8')
    expected = '<form id="historical-report-rebuild-form" method="post" action="rebuild-historical-report"><input type="text" name="month" value="{esc(default_month.replace(\'-\', \'_\'))}" pattern="[0-9]{4}_(0[1-9]|1[0-2])" placeholder="YYYY_MM" required>'
    assert expected in source
