import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import assistant_fast_context as afc


def _write_snapshot(folder: Path, stamp: str, value: float) -> None:
    payload = {
        'entities': [
            {'entity_id': 'sensor.a', 'state': str(value), 'last_updated': stamp},
            {'entity_id': 'sensor.b', 'state': str(value + 10), 'last_updated': stamp},
        ]
    }
    (folder / f'home_assistant_quarter_{stamp}.json').write_text(json.dumps(payload), encoding='utf-8')


def test_quarter_hour_cache_reuses_validated_files_and_reads_only_new_snapshots(tmp_path, monkeypatch):
    folder = tmp_path / '01_Input' / '2026_08' / 'HomeAssistant' / 'QuarterHour'
    folder.mkdir(parents=True)
    _write_snapshot(folder, '20260816T200000Z', 1.0)
    _write_snapshot(folder, '20260816T201500Z', 2.0)

    afc.clear_quarter_hour_series_cache()
    reads = []
    original = Path.read_text

    def counted_read_text(self, *args, **kwargs):
        if self.parent == folder and self.name.startswith('home_assistant_quarter_'):
            reads.append(self.name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', counted_read_text)

    first = afc.load_quarter_hour_series_once(tmp_path, '2026_08', ['sensor.a', 'sensor.b'])
    assert len(first['sensor.a']) == 2
    assert len(reads) == 2

    second = afc.load_quarter_hour_series_once(tmp_path, '2026_08', ['sensor.a', 'sensor.b'])
    assert len(second['sensor.a']) == 2
    assert len(reads) == 2, 'cached call must not re-read existing snapshots'

    _write_snapshot(folder, '20260816T203000Z', 3.0)
    third = afc.load_quarter_hour_series_once(tmp_path, '2026_08', ['sensor.a', 'sensor.b'])
    assert len(third['sensor.a']) == 3
    assert reads.count('home_assistant_quarter_20260816T203000Z.json') == 1
    assert len(reads) == 3, 'only the newly appended snapshot may be read'


def test_startup_probe_prewarms_current_quarter_hour_cache_before_http_acceptance():
    main = (APP / 'main.py').read_text(encoding='utf-8')
    assert 'prewarm_assistant_quarter_hour_cache' in main
    probe_pos = main.index('result = run_assistant_runtime_probe(app_version=APP_VERSION)')
    prewarm_pos = main.rindex('prewarm_assistant_quarter_hour_cache', 0, probe_pos)
    assert prewarm_pos < probe_pos
