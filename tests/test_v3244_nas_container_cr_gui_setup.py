from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


def test_panel_is_read_only_local_capability_and_has_no_tls_setup(tmp_path):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    capability = project / 'Inbox/nas_container_cr_local/capability.json'
    capability.parent.mkdir(parents=True)
    capability.write_text(json.dumps({
        'schema': 'energie_nas_container_cr_local_capability_v1',
        'ready': True, 'status': 'GREEN', 'version': '32.4.36',
    }), encoding='utf-8')
    panel = web.render_nas_container_cr_setup(project)
    assert 'NAS Container Crash Recovery' in panel
    assert 'Gereed' in panel
    for forbidden in ('certificate_bundle', '2376', 'projectmanager-nas-cr-activate', 'Activeer ChatGPT-koppeling'):
        assert forbidden not in panel


def test_panel_is_not_ready_without_fresh_capability_marker(tmp_path):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    project.mkdir()
    panel = web.render_nas_container_cr_setup(project)
    assert 'Niet gereed' in panel
    assert 'fail-closed' in panel


def test_active_web_post_surface_contains_only_decision_route_for_pmv2():
    import projectmanager_web as web

    source = inspect.getsource(web.install_projectmanager_web)
    assert 'projectmanager-decision' in source
    assert 'projectmanager-nas-cr-setup' not in source
    assert 'projectmanager-nas-cr-activate' not in source
    assert 'certificate_bundle' not in source


def test_legacy_tls_helpers_are_not_called_by_active_install_surface():
    import projectmanager_web as web

    source = inspect.getsource(web.install_projectmanager_web) + inspect.getsource(web.render_nas_container_cr_setup)
    assert 'install_nas_docker_tls_bundle' not in source
    assert 'activate_projectmanager_connector' not in source
    assert 'DockerEngineTlsClient' not in source
