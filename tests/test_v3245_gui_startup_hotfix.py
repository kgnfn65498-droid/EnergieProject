from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'


def test_projectmanager_web_imports_in_real_mode_entrypoint_context():
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(APP)!r}); "
        "import projectmanager_v2.projectmanager_web; print('PM_WEB_IMPORT_OK')"
    )
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'PM_WEB_IMPORT_OK' in result.stdout


def test_mode_gui_ajax_posts_urlencoded_not_multipart():
    source = (APP / 'operating_mode_web.py').read_text(encoding='utf-8')
    assert 'body: new URLSearchParams(new FormData(form))' in source
    assert 'body: new FormData(form)' not in source
