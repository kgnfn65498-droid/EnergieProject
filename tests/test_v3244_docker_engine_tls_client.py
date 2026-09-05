from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


class DummyConfig:
    host = 'nas.local'
    port = 2376
    def ssl_context(self):
        return object()


class FakeResponse:
    def __init__(self, status=200, body=b'', headers=None):
        self.status = status
        self.reason = 'OK' if status < 400 else 'ERR'
        self._body = io.BytesIO(body)
        self._headers = headers or {}
    def read(self, amount=-1):
        return self._body.read(amount)
    def getheader(self, name, default=None):
        return self._headers.get(name, default)


class FakeConnection:
    responses = []
    calls = []
    def __init__(self, host, port, context=None, timeout=None):
        self.host, self.port, self.context, self.timeout = host, port, context, timeout
    def request(self, method, path, body=None, headers=None):
        self.__class__.calls.append((method, path, body, headers or {}))
    def getresponse(self):
        return self.__class__.responses.pop(0)
    def close(self):
        return None


def test_client_has_no_generic_exec_or_mutation_surface():
    from docker_engine_tls_client import DockerEngineTlsClient

    public = {name for name in dir(DockerEngineTlsClient) if not name.startswith('_')}
    for forbidden in {'exec', 'run', 'request', 'container_stop', 'container_restart', 'image_remove'}:
        assert forbidden not in public


def test_client_uses_only_fixed_ping_and_inspect_endpoints(monkeypatch):
    import docker_engine_tls_client as mod

    FakeConnection.calls = []
    FakeConnection.responses = [
        FakeResponse(200, b'OK'),
        FakeResponse(200, json.dumps({'Id': 'abc', 'Config': {'Image': 'python:3.12-slim'}}).encode()),
    ]
    monkeypatch.setattr(mod.http.client, 'HTTPSConnection', FakeConnection)
    client = mod.DockerEngineTlsClient(DummyConfig())
    assert client.ping()['ok'] is True
    assert client.container_inspect('energie-release-watcher')['Id'] == 'abc'
    assert FakeConnection.calls[0][0:2] == ('GET', '/_ping')
    assert FakeConnection.calls[1][0:2] == ('GET', '/v1.41/containers/energie-release-watcher/json')


def test_client_rejects_container_path_injection():
    from docker_engine_tls_client import DockerEngineTlsClient

    client = DockerEngineTlsClient(DummyConfig())
    with pytest.raises(ValueError):
        client.container_inspect('../bad?x=1')


def test_connector_reload_is_hardcoded_to_filesystem_mcp(monkeypatch):
    import docker_engine_tls_client as mod

    FakeConnection.calls = []
    FakeConnection.responses = [FakeResponse(204, b'')]
    monkeypatch.setattr(mod.http.client, 'HTTPSConnection', FakeConnection)
    client = mod.DockerEngineTlsClient(DummyConfig())
    result = client.reload_projectmanager_connector()
    assert result['ok'] is True
    assert FakeConnection.calls == [
        ('POST', '/v1.41/containers/energie-filesystem-mcp/restart?t=10', None, {'Accept': 'application/json'})
    ]


def test_probe_mutations_reject_non_probe_container_names():
    from docker_engine_tls_client import DockerEngineTlsClient

    client = DockerEngineTlsClient(DummyConfig())
    with pytest.raises(ValueError, match='probe'):
        client.container_create_probe('python:3.12-slim', 'energie-filesystem-mcp')
    with pytest.raises(ValueError, match='probe'):
        client.container_remove_probe('energie-filesystem-mcp')
