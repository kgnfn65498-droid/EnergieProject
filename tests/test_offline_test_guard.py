import socket
import subprocess
import sys
from pathlib import Path

import pytest

from offline_test_guard import (
    guarded_connect,
    guarded_connect_ex,
    guarded_create_connection,
    guarded_getaddrinfo,
)


ROOT = Path(__file__).resolve().parents[1]


def test_external_address_is_rejected_before_delegate_runs():
    calls = []

    def delegate(sock, address):
        calls.append((sock, address))
        return 0

    with pytest.raises(PermissionError, match="OFFLINE_TEST_GUARD"):
        guarded_connect(delegate, object(), ("192.168.1.200", 8000))

    assert calls == []


def test_loopback_address_is_delegated_unchanged():
    calls = []
    sentinel = object()

    def delegate(sock, address):
        calls.append((sock, address))
        return 17

    assert guarded_connect(delegate, sentinel, ("127.0.0.1", 8123)) == 17
    assert calls == [(sentinel, ("127.0.0.1", 8123))]


def test_connect_ex_rejects_external_address_before_delegate_runs():
    calls = []

    def delegate(sock, address):
        calls.append((sock, address))
        return 0

    assert guarded_connect_ex(delegate, object(), ("192.168.1.200", 8000)) != 0
    assert calls == []


def test_create_connection_rejects_external_hostname_before_dns_or_delegate():
    calls = []

    def delegate(address, *args, **kwargs):
        calls.append((address, args, kwargs))
        return object()

    with pytest.raises(PermissionError, match="OFFLINE_TEST_GUARD"):
        guarded_create_connection(delegate, ("nas.invalid", 8000), timeout=1)

    assert calls == []


def test_dns_resolution_rejects_external_hostname_before_delegate():
    calls = []

    def delegate(*args, **kwargs):
        calls.append((args, kwargs))
        return []

    with pytest.raises(PermissionError, match="OFFLINE_TEST_GUARD"):
        guarded_getaddrinfo(delegate, "nas.invalid", 8000)

    assert calls == []


def test_child_python_installs_guard_before_application_imports():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import socket; print(getattr(socket.socket.connect, "
            "'_energie_offline_guard', False))",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_pytest_session_installs_external_network_guard():
    assert getattr(socket.socket.connect, "_energie_offline_guard", False) is True
