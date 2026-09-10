from __future__ import annotations

import http.client
import json
import os
import socket
from pathlib import Path
from urllib.parse import quote, urlencode


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


class DockerEngineUnixClient:
    """Small allowlisted Docker Engine client for the trusted local CR executor."""

    def __init__(self, socket_path: str = '/var/run/docker.sock', *, timeout_seconds: float = 30.0):
        self._socket_path = str(socket_path)
        self._timeout = max(1.0, float(timeout_seconds))

    def _response(self, method: str, path: str, *, body: bytes | None = None, headers: dict[str, str] | None = None):
        conn = _UnixHTTPConnection(self._socket_path, self._timeout)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return conn, response
        except Exception:
            conn.close()
            raise

    @staticmethod
    def _json_response(conn: http.client.HTTPConnection, response: http.client.HTTPResponse, *, missing_ok: bool = False):
        try:
            payload = response.read()
            if missing_ok and response.status == 404:
                return None
            if not 200 <= response.status < 300:
                detail = payload.decode('utf-8', errors='replace')[:500]
                raise RuntimeError(f'Docker Engine HTTP {response.status}: {detail}')
            if not payload:
                return {'ok': True}
            value = json.loads(payload.decode('utf-8'))
            return value
        finally:
            conn.close()

    @staticmethod
    def _validate_probe_name(name: str) -> str:
        value = str(name)
        if not value.startswith('nas-cr-probe-') or '/' in value or '\\' in value:
            raise ValueError('Alleen nas-cr-probe-* containers zijn toegestaan')
        return value

    def ping(self):
        conn, response = self._response('GET', '/_ping')
        try:
            payload = response.read().decode('utf-8', errors='replace').strip()
            if response.status != 200 or payload != 'OK':
                raise RuntimeError(f'Docker Engine ping mislukt: HTTP {response.status} {payload[:100]}')
            return {'ok': True, 'transport': 'unix_socket'}
        finally:
            conn.close()

    def container_inspect(self, name):
        safe = quote(str(name), safe='')
        conn, response = self._response('GET', f'/containers/{safe}/json')
        return self._json_response(conn, response, missing_ok=True)

    def image_inspect(self, name):
        safe = quote(str(name), safe='')
        conn, response = self._response('GET', f'/images/{safe}/json')
        return self._json_response(conn, response)

    def image_export(self, names, destination):
        images = [str(item).strip() for item in names if str(item).strip()]
        if not images:
            raise ValueError('Geen images opgegeven voor NAS CR export')
        query = urlencode([('names', item) for item in images])
        conn, response = self._response('GET', f'/images/get?{query}')
        destination = Path(destination)
        temp = destination.with_name(destination.name + f'.tmp-{os.getpid()}')
        written = 0
        try:
            if not 200 <= response.status < 300:
                detail = response.read().decode('utf-8', errors='replace')[:500]
                raise RuntimeError(f'Docker image export mislukt: HTTP {response.status}: {detail}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with temp.open('wb') as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            if written <= 0:
                raise RuntimeError('Docker image export is leeg')
            os.replace(temp, destination)
            return {'ok': True, 'bytes': written, 'images': images}
        finally:
            conn.close()
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def container_create_probe(self, image, name):
        probe_name = self._validate_probe_name(name)
        payload = json.dumps({
            'Image': str(image),
            'NetworkDisabled': True,
            'HostConfig': {'NetworkMode': 'none'},
        }, separators=(',', ':')).encode('utf-8')
        path = '/containers/create?' + urlencode({'name': probe_name})
        conn, response = self._response(
            'POST', path, body=payload, headers={'Content-Type': 'application/json', 'Content-Length': str(len(payload))}
        )
        return self._json_response(conn, response)

    def container_remove_probe(self, name):
        probe_name = self._validate_probe_name(name)
        safe = quote(probe_name, safe='')
        conn, response = self._response('DELETE', f'/containers/{safe}?force=1&v=1')
        result = self._json_response(conn, response)
        if isinstance(result, dict):
            return {**result, 'ok': True, 'name': probe_name}
        return {'ok': True, 'name': probe_name}
