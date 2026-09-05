from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


def test_tls_config_rejects_project_root_material(tmp_path):
    from nas_docker_tls import DockerTlsConfig

    project = tmp_path / 'EnergieProject'
    private = project / 'docker_tls'
    private.mkdir(parents=True)
    (private / 'host.txt').write_text('192.168.1.200\n')
    for name in ('ca.pem', 'cert.pem', 'key.pem'):
        (private / name).write_text('dummy')
    with pytest.raises(RuntimeError, match='private add-ondata'):
        DockerTlsConfig.load(private, project_root=project)


def test_tls_config_requires_host_ca_cert_and_key(tmp_path):
    from nas_docker_tls import DockerTlsConfig

    with pytest.raises(RuntimeError, match='ontbreekt'):
        DockerTlsConfig.load(tmp_path, project_root=tmp_path / 'project')


def test_tls_config_rejects_nonstandard_port(tmp_path):
    from nas_docker_tls import DockerTlsConfig

    with pytest.raises(ValueError, match='2376'):
        DockerTlsConfig(private_root=tmp_path, host='nas.local', port=2375,
                        ca_path=tmp_path/'ca.pem', cert_path=tmp_path/'cert.pem', key_path=tmp_path/'key.pem')
