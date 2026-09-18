from pathlib import Path
from types import SimpleNamespace


def test_projectmanager_success_clears_failure_marker_and_dismisses_persistent_notification(tmp_path: Path, monkeypatch):
    import projectmanager_v2_entrypoint as mod

    system_root = tmp_path / 'RuntimeV2'
    failure = system_root / 'self_audit' / 'embedded_failure.json'
    failure.parent.mkdir(parents=True)
    failure.write_text('{"status":"RED"}\n', encoding='utf-8')

    requests = []

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=0):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setenv('SUPERVISOR_TOKEN', 'token')
    monkeypatch.setattr(mod.urllib.request, 'urlopen', fake_urlopen)

    mod._mark_success(SimpleNamespace(system_root=str(system_root)))

    assert not failure.exists()
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url.endswith('/persistent_notification/dismiss')
    assert b'energie_projectmanager_self_failure' in (request.data or b'')
    assert timeout == 5
