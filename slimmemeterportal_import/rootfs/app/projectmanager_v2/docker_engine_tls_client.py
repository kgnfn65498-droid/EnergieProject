from __future__ import annotations

import http.client
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

API_PREFIX = '/v1.41'
MAX_JSON_BYTES = 2 * 1024 * 1024
_CONTAINER_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
_IMAGE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,511}$')


def _container_name(value: str) -> str:
    name = str(value or '').strip()
    if not _CONTAINER_RE.fullmatch(name):
        raise ValueError('Ongeldige containernaam')
    return name


def _probe_name(value: str) -> str:
    name = _container_name(value)
    if not name.startswith('nas-cr-probe-'):
        raise ValueError('Alleen nas-cr-probe containers zijn toegestaan voor probe-mutaties')
    return name


def _image_name(value: str) -> str:
    name = str(value or '').strip()
    if not _IMAGE_RE.fullmatch(name) or '..' in name or '//' in name:
        raise ValueError('Ongeldige Docker image-referentie')
    return name


class DockerEngineTlsClient:
    """Narrow Docker Engine TLS client; intentionally no generic request surface."""

    def __init__(self, config, *, timeout_seconds: float = 20.0):
        self._config = config
        self._timeout = max(1.0, min(float(timeout_seconds), 120.0))

    def _connection(self, *, timeout: float | None = None):
        return http.client.HTTPSConnection(
            self._config.host,
            self._config.port,
            context=self._config.ssl_context(),
            timeout=self._timeout if timeout is None else timeout,
        )

    @staticmethod
    def _bounded_read(response, *, limit: int = MAX_JSON_BYTES) -> bytes:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise RuntimeError('Docker Engine-response overschrijdt limiet')
        return data

    def _json_call(self, method: str, path: str, *, body: dict[str, Any] | None = None,
                   expected: tuple[int, ...] = (200,), allow_not_found: bool = False):
        payload = None
        headers = {'Accept': 'application/json'}
        if body is not None:
            payload = json.dumps(body, separators=(',', ':')).encode('utf-8')
            headers['Content-Type'] = 'application/json'
            headers['Content-Length'] = str(len(payload))
        conn = self._connection()
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            raw = self._bounded_read(response)
            if allow_not_found and response.status == 404:
                return None
            if response.status not in expected:
                detail = raw[:512].decode('utf-8', errors='replace')
                raise RuntimeError(f'Docker Engine {method} {path} -> HTTP {response.status}: {detail}')
            if not raw:
                return {}
            try:
                return json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError('Docker Engine gaf ongeldige JSON') from exc
        finally:
            conn.close()

    def ping(self) -> dict[str, Any]:
        conn = self._connection()
        try:
            conn.request('GET', '/_ping', headers={'Accept': 'text/plain'})
            response = conn.getresponse()
            raw = self._bounded_read(response, limit=1024)
            if response.status != 200 or raw.strip() != b'OK':
                raise RuntimeError(f'Docker TLS ping mislukt: HTTP {response.status}')
            return {'ok': True, 'host': self._config.host, 'port': self._config.port}
        finally:
            conn.close()

    def container_inspect(self, name: str) -> dict[str, Any] | None:
        safe = _container_name(name)
        return self._json_call(
            'GET', f'{API_PREFIX}/containers/{quote(safe, safe="")}/json', allow_not_found=True
        )

    def image_inspect(self, name: str) -> dict[str, Any]:
        safe = _image_name(name)
        result = self._json_call('GET', f'{API_PREFIX}/images/{quote(safe, safe="")}/json')
        if not isinstance(result, dict):
            raise RuntimeError('Docker image inspect gaf ongeldig resultaat')
        return result

    def image_export(self, names: list[str], destination: Path | str) -> dict[str, Any]:
        unique: list[str] = []
        for value in names:
            safe = _image_name(value)
            if safe not in unique:
                unique.append(safe)
        if not unique or len(unique) > 32:
            raise ValueError('Docker image export vereist 1..32 vaste images')
        query = urlencode([('names', name) for name in unique])
        path = f'{API_PREFIX}/images/get?{query}'
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + f'.tmp-{os.getpid()}')
        conn = self._connection(timeout=900.0)
        total = 0
        try:
            conn.request('GET', path, headers={'Accept': 'application/x-tar'})
            response = conn.getresponse()
            if response.status != 200:
                raw = self._bounded_read(response, limit=4096)
                raise RuntimeError(
                    f'Docker image export -> HTTP {response.status}: {raw.decode("utf-8", errors="replace")}'
                )
            with temp.open('wb') as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    total += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            if total <= 0:
                raise RuntimeError('Docker image export is leeg')
            os.replace(temp, target)
            return {'ok': True, 'bytes': total, 'images': unique, 'path': str(target)}
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            conn.close()

    def container_create_probe(self, image: str, name: str) -> dict[str, Any]:
        safe_image = _image_name(image)
        safe_name = _probe_name(name)
        query = urlencode({'name': safe_name})
        result = self._json_call(
            'POST',
            f'{API_PREFIX}/containers/create?{query}',
            body={'Image': safe_image, 'NetworkDisabled': True, 'Labels': {'energie.cr_probe': 'true'}},
            expected=(201,),
        )
        if not isinstance(result, dict) or not result.get('Id'):
            raise RuntimeError('Docker probe-container create gaf geen Id')
        return result

    def container_remove_probe(self, name: str) -> dict[str, Any]:
        safe_name = _probe_name(name)
        result = self._json_call(
            'DELETE',
            f'{API_PREFIX}/containers/{quote(safe_name, safe="")}?v=1&force=1',
            expected=(204,),
        )
        return {'ok': True, 'name': safe_name, 'result': result}


    @staticmethod
    def _watcher_checks(info: dict[str, Any]) -> dict[str, bool]:
        config=info.get('Config') or {}; host=info.get('HostConfig') or {}; state=info.get('State') or {}
        env=set(config.get('Env') or []); mounts=info.get('Mounts') or []
        mount_map={str(m.get('Destination') or ''):str(m.get('Source') or '') for m in mounts if isinstance(m,dict)}
        return {'running':state.get('Running') is True,'image':str(config.get('Image') or '')=='python:3.12-slim','command':list(config.get('Cmd') or [])==['sh','/energy/App/tools/release_watcher.sh'],'contract_env':'ENERGIE_WATCHER_CONTAINER_CONTRACT=3' in env,'network_none':str(host.get('NetworkMode') or '')=='none','cap_drop':set(host.get('CapDrop') or [])=={'ALL'},'cap_add':set(host.get('CapAdd') or [])=={'DAC_OVERRIDE','DAC_READ_SEARCH','FOWNER'},'security':any('no-new-privileges' in str(v) for v in (host.get('SecurityOpt') or [])),'restart':str((host.get('RestartPolicy') or {}).get('Name') or '')=='unless-stopped','energy_mount':bool(mount_map.get('/energy')),'docker_socket':mount_map.get('/var/run/docker.sock')=='/var/run/docker.sock'}

    def recreate_release_watcher(self) -> dict[str, Any]:
        name='energie-release-watcher'; current=self.container_inspect(name)
        if not isinstance(current,dict): raise RuntimeError('existing watcher required to prove fixed /energy host source')
        energy_source=''
        for mount in current.get('Mounts') or []:
            if isinstance(mount,dict) and mount.get('Destination')=='/energy': energy_source=str(mount.get('Source') or ''); break
        if not energy_source or not energy_source.rstrip('/').endswith('/EnergieProject'): raise RuntimeError('watcher /energy host source is not a proven EnergieProject path')
        if all(self._watcher_checks(current).values()): return {'ok':True,'recreated':False,'container':name,'contract':self._watcher_checks(current)}
        self.image_inspect('python:3.12-slim')
        self._json_call('DELETE',f'{API_PREFIX}/containers/{quote(name,safe="")}?v=1&force=1',expected=(204,))
        body={'Image':'python:3.12-slim','Cmd':['sh','/energy/App/tools/release_watcher.sh'],'Env':['ENERGIE_ROOT=/energy','ENERGIE_WATCH_INTERVAL=5','ENERGIE_ZIP_STABLE_POLLS=3','ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS=30','ENERGIE_WATCHER_CONTAINER_CONTRACT=3','ENERGIE_BACKUP_RETENTION=999','ENERGIE_PROCESSED_RETENTION=999'],'HostConfig':{'Binds':[f'{energy_source}:/energy','/var/run/docker.sock:/var/run/docker.sock'],'RestartPolicy':{'Name':'unless-stopped'},'NetworkMode':'none','CapDrop':['ALL'],'CapAdd':['DAC_OVERRIDE','DAC_READ_SEARCH','FOWNER'],'SecurityOpt':['no-new-privileges']}}
        created=self._json_call('POST',f'{API_PREFIX}/containers/create?{urlencode({"name":name})}',body=body,expected=(201,))
        if not isinstance(created,dict) or not created.get('Id'): raise RuntimeError('watcher recreate returned no container id')
        self._json_call('POST',f'{API_PREFIX}/containers/{quote(name,safe="")}/start',expected=(204,))
        info=self.container_inspect(name) or {}; checks=self._watcher_checks(info)
        if not all(checks.values()): raise RuntimeError('watcher recreate inspect contract mismatch: '+','.join(k for k,v in checks.items() if not v))
        return {'ok':True,'recreated':True,'container':name,'contract':checks,'energy_source':energy_source}

    def reload_projectmanager_connector(self) -> dict[str, Any]:
        """One bounded restart used only after explicit GUI activation."""
        self._json_call(
            'POST',
            f'{API_PREFIX}/containers/energie-filesystem-mcp/restart?t=10',
            expected=(204,),
        )
        return {'ok': True, 'container': 'energie-filesystem-mcp'}
