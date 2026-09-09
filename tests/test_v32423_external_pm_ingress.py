from __future__ import annotations

import importlib.util
import io
import json
import sys
from http import HTTPStatus
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
MAIN = APP / 'main.py'
MODULE = APP / 'projectmanager_external_ingress.py'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def load_external_module():
    assert MODULE.is_file(), 'external PM ingress module must exist'
    spec = importlib.util.spec_from_file_location('projectmanager_external_ingress_v32423', MODULE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_main(name='main_v32423_external_ingress'):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def good_env():
    return {
        'PM_EXTERNAL_INGRESS_SECRET': 's' * 48,
        'PM_EXTERNAL_ALLOWED_PRINCIPAL': 'Peter',
    }


def good_headers(*, client='voice', principal='Peter', secret=None):
    return {
        'X-Energie-Edge-Secret': secret or ('s' * 48),
        'X-Energie-Principal': principal,
        'X-Energie-Client': client,
    }


def test_external_auth_is_deny_by_default_without_server_secret():
    module = load_external_module()
    with pytest.raises(PermissionError, match='not configured'):
        module.authenticate_external_pm_request(good_headers(), {})


def test_external_auth_rejects_wrong_secret_principal_and_client():
    module = load_external_module()
    with pytest.raises(PermissionError, match='credentials'):
        module.authenticate_external_pm_request(good_headers(secret='x' * 48), good_env())
    with pytest.raises(PermissionError, match='principal'):
        module.authenticate_external_pm_request(good_headers(principal='Mallory'), good_env())
    with pytest.raises(PermissionError, match='client'):
        module.authenticate_external_pm_request(good_headers(client='browser'), good_env())


def test_external_auth_maps_authenticated_client_to_trusted_source_channel():
    module = load_external_module()
    auth = module.authenticate_external_pm_request(good_headers(client='voice'), good_env())
    assert auth == {'principal': 'Peter', 'client': 'voice', 'source_channel': 'voice'}


def test_external_payload_cannot_override_trusted_source_identity():
    module = load_external_module()
    auth = {'principal': 'Peter', 'client': 'voice', 'source_channel': 'voice'}
    with pytest.raises(ValueError, match='unsupported external projectmanager payload fields'):
        module.parse_external_pm_payload({'query': 'status', 'source_channel': 'nomad'}, auth)
    parsed = module.parse_external_pm_payload({'query': 'status', 'session_id': 's1'}, auth)
    assert parsed['source_channel'] == 'voice'
    assert parsed['query'] == 'status'


def test_main_dedicated_external_route_uses_server_authenticated_channel(monkeypatch):
    m = load_main('main_v32423_external_route')
    monkeypatch.setenv('PM_EXTERNAL_INGRESS_SECRET', 's' * 48)
    monkeypatch.setenv('PM_EXTERNAL_ALLOWED_PRINCIPAL', 'Peter')
    calls = []
    audits = []
    monkeypatch.setattr(m, 'append_audit_event', lambda *args, **kwargs: audits.append((args, kwargs)))
    monkeypatch.setattr(
        m,
        'respond_projectmanager_conversation',
        lambda query, **kwargs: calls.append((query, kwargs)) or {'status': 'answered'},
    )

    payload = json.dumps({'query': 'status', 'session_id': 'remote1'}).encode('utf-8')
    handler = object.__new__(m.Handler)
    handler.path = '/api/projectmanager/external/conversation'
    handler.headers = {
        'Content-Length': str(len(payload)),
        'X-Energie-Edge-Secret': 's' * 48,
        'X-Energie-Principal': 'Peter',
        'X-Energie-Client': 'voice',
    }
    handler.rfile = io.BytesIO(payload)
    responses = []
    handler.send_body = lambda status, body, content_type, disposition=None: responses.append((status, json.loads(body), content_type))

    m.Handler.do_POST(handler)

    assert responses[0][0] == HTTPStatus.OK
    assert calls[0][0] == 'status'
    assert calls[0][1]['source_channel'] == 'voice'
    assert calls[0][1]['force'] is True
    assert audits and audits[0][0][0] == 'external_pm_ingress'
    assert audits[0][1]['details']['principal'] == 'Peter'
    assert 'secret' not in json.dumps(audits[0]).lower()


def test_main_external_route_rejects_forged_source_channel_field(monkeypatch):
    m = load_main('main_v32423_external_route_forged')
    monkeypatch.setenv('PM_EXTERNAL_INGRESS_SECRET', 's' * 48)
    monkeypatch.setenv('PM_EXTERNAL_ALLOWED_PRINCIPAL', 'Peter')
    payload = json.dumps({'query': 'status', 'source_channel': 'nomad'}).encode('utf-8')
    handler = object.__new__(m.Handler)
    handler.path = '/api/projectmanager/external/conversation'
    handler.headers = {
        'Content-Length': str(len(payload)),
        'X-Energie-Edge-Secret': 's' * 48,
        'X-Energie-Principal': 'Peter',
        'X-Energie-Client': 'voice',
    }
    handler.rfile = io.BytesIO(payload)
    responses = []
    handler.send_body = lambda status, body, content_type, disposition=None: responses.append((status, json.loads(body), content_type))

    m.Handler.do_POST(handler)

    assert responses[0][0] == HTTPStatus.BAD_REQUEST
    assert 'unsupported external projectmanager payload fields' in responses[0][1]['error']
