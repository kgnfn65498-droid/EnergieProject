from __future__ import annotations

import io
import json
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


def make_bundle(*, key=b'PRIVATE_KEY_SENTINEL') -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr('docker/ca.pem', b'CA_CERT')
        z.writestr('docker/cert.pem', b'CLIENT_CERT')
        z.writestr('docker/key.pem', key)
    return out.getvalue()


class FakeConfig:
    host = '192.168.1.200'
    port = 2376


class FakeClient:
    def __init__(self, config):
        self.config = config
    def ping(self):
        return {'ok': True, 'host': self.config.host, 'port': self.config.port}
    def reload_projectmanager_connector(self):
        return {'ok': True, 'container': 'energie-filesystem-mcp'}


def test_tls_bundle_setup_writes_only_private_addon_data(tmp_path, monkeypatch):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    project.mkdir()
    private = tmp_path / 'addon-private' / 'docker_tls'
    monkeypatch.setattr(web.DockerTlsConfig, 'load', classmethod(lambda cls, private_root, project_root=None: FakeConfig()))

    result = web.install_nas_docker_tls_bundle(
        project_root=project,
        private_root=private,
        host='192.168.1.200',
        bundle=make_bundle(),
        client_cls=FakeClient,
    )

    assert result['ready'] is True
    assert (private / 'host.txt').read_text().strip() == '192.168.1.200'
    assert (private / 'ca.pem').read_bytes() == b'CA_CERT'
    assert (private / 'cert.pem').read_bytes() == b'CLIENT_CERT'
    assert (private / 'key.pem').read_bytes() == b'PRIVATE_KEY_SENTINEL'
    assert not list(project.rglob('*.pem'))
    assert stat.S_IMODE((private / 'key.pem').stat().st_mode) == 0o600


def test_rendered_panel_never_returns_private_key_contents(tmp_path):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    project.mkdir()
    private = tmp_path / 'private' / 'docker_tls'
    private.mkdir(parents=True)
    (private / 'key.pem').write_text('PRIVATE_KEY_SENTINEL')
    (private / 'status.json').write_text(json.dumps({'ready': True, 'host': '192.168.1.200'}))

    html = web.render_nas_container_cr_setup(project, private_root=private)
    assert 'NAS Container Crash Recovery' in html
    assert 'certificate_bundle' in html
    assert 'nas_host' in html
    assert 'PRIVATE_KEY_SENTINEL' not in html
    assert '/data/' not in html
    assert str(private) not in html


def test_ready_panel_offers_bounded_connector_activation(tmp_path):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    project.mkdir()
    private = tmp_path / 'private' / 'docker_tls'
    private.mkdir(parents=True)
    (private / 'status.json').write_text(json.dumps({'ready': True, 'host': '192.168.1.200'}))
    panel = web.render_nas_container_cr_setup(project, private_root=private)
    assert 'projectmanager-nas-cr-activate' in panel
    assert 'energie-filesystem-mcp' in panel


def test_connector_activation_uses_only_hardcoded_reload(tmp_path, monkeypatch):
    import projectmanager_web as web

    project = tmp_path / 'EnergieProject'
    project.mkdir()
    private = tmp_path / 'private' / 'docker_tls'
    private.mkdir(parents=True)
    (private / 'status.json').write_text(json.dumps({'ready': True, 'host': '192.168.1.200'}))
    monkeypatch.setattr(web.DockerTlsConfig, 'load', classmethod(lambda cls, private_root, project_root=None: FakeConfig()))
    result = web.activate_projectmanager_connector(
        project_root=project,
        private_root=private,
        client_cls=FakeClient,
    )
    assert result == {'ok': True, 'container': 'energie-filesystem-mcp'}
