"""Fail-closed network boundary for the repository's pytest suite."""

from __future__ import annotations

import errno
import ipaddress
import socket
from typing import Any, Callable


def _is_loopback_address(address: Any) -> bool:
    if not isinstance(address, tuple) or not address:
        return True  # Unix-domain sockets and other non-network addresses.
    host = address[0]
    if not isinstance(host, str):
        return False
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_local_lookup(host: Any) -> bool:
    if host is None:
        return True
    if not isinstance(host, str):
        return False
    normalized = host.strip().lower()
    if normalized in {"localhost", "0.0.0.0", "::", ""}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _blocked(address: Any) -> PermissionError:
    return PermissionError(
        errno.EACCES,
        f"OFFLINE_TEST_GUARD blocked external socket address {address!r}",
    )


def guarded_connect(delegate: Callable[..., Any], sock: Any, address: Any) -> Any:
    if not _is_loopback_address(address):
        raise _blocked(address)
    return delegate(sock, address)


def guarded_connect_ex(delegate: Callable[..., int], sock: Any, address: Any) -> int:
    if not _is_loopback_address(address):
        return errno.EACCES
    return delegate(sock, address)


def guarded_create_connection(
    delegate: Callable[..., Any], address: Any, *args: Any, **kwargs: Any
) -> Any:
    if not _is_loopback_address(address):
        raise _blocked(address)
    return delegate(address, *args, **kwargs)


def guarded_getaddrinfo(
    delegate: Callable[..., Any], host: Any, port: Any, *args: Any, **kwargs: Any
) -> Any:
    if not _is_local_lookup(host):
        raise _blocked((host, port))
    return delegate(host, port, *args, **kwargs)


def install_offline_guard() -> None:
    if getattr(socket.socket.connect, "_energie_offline_guard", False):
        return

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def connect(sock: Any, address: Any) -> Any:
        return guarded_connect(original_connect, sock, address)

    def connect_ex(sock: Any, address: Any) -> int:
        return guarded_connect_ex(original_connect_ex, sock, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        return guarded_create_connection(
            original_create_connection, address, *args, **kwargs
        )

    def getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        return guarded_getaddrinfo(
            original_getaddrinfo, host, port, *args, **kwargs
        )

    connect._energie_offline_guard = True  # type: ignore[attr-defined]
    connect_ex._energie_offline_guard = True  # type: ignore[attr-defined]
    create_connection._energie_offline_guard = True  # type: ignore[attr-defined]
    getaddrinfo._energie_offline_guard = True  # type: ignore[attr-defined]
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo

