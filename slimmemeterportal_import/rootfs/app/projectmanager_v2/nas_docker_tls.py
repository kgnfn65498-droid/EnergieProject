from __future__ import annotations

import ipaddress
import ssl
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PRIVATE_ROOT = Path('/data/projectmanager_v2/docker_tls')
DOCKER_TLS_PORT = 2376
_REQUIRED = ('host.txt', 'ca.pem', 'cert.pem', 'key.pem')


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_host(host: str) -> str:
    value = str(host or '').strip()
    if not value:
        raise ValueError('NAS-host ontbreekt')
    if any(ord(ch) < 32 for ch in value) or any(ch in value for ch in '/\\?#@:'):
        raise ValueError('NAS-host bevat onveilige tekens')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    labels = value.split('.')
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError('NAS-host is ongeldig')
    for label in labels:
        if label[0] == '-' or label[-1] == '-' or not all(ch.isalnum() or ch == '-' for ch in label):
            raise ValueError('NAS-host is ongeldig')
    return value


@dataclass(frozen=True)
class DockerTlsConfig:
    private_root: Path
    host: str
    port: int
    ca_path: Path
    cert_path: Path
    key_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, 'private_root', Path(self.private_root))
        object.__setattr__(self, 'ca_path', Path(self.ca_path))
        object.__setattr__(self, 'cert_path', Path(self.cert_path))
        object.__setattr__(self, 'key_path', Path(self.key_path))
        object.__setattr__(self, 'host', _validate_host(self.host))
        if int(self.port) != DOCKER_TLS_PORT:
            raise ValueError('Alleen QNAP Docker TLS-poort 2376 is toegestaan')
        object.__setattr__(self, 'port', DOCKER_TLS_PORT)

    @classmethod
    def load(
        cls,
        private_root: Path | str = DEFAULT_PRIVATE_ROOT,
        *,
        project_root: Path | str | None = None,
    ) -> 'DockerTlsConfig':
        private = Path(private_root)
        if project_root is not None and _is_within(private, Path(project_root)):
            raise RuntimeError('Docker TLS-materiaal moet in private add-ondata staan, niet in het EnergieProject')
        missing = [name for name in _REQUIRED if not (private / name).is_file()]
        if missing:
            raise RuntimeError('Docker TLS-config ontbreekt: ' + ', '.join(missing))
        for name in _REQUIRED:
            if (private / name).is_symlink():
                raise RuntimeError(f'Docker TLS-config bevat onveilige symlink: {name}')
        host = (private / 'host.txt').read_text(encoding='utf-8').strip()
        return cls(
            private_root=private,
            host=host,
            port=DOCKER_TLS_PORT,
            ca_path=private / 'ca.pem',
            cert_path=private / 'cert.pem',
            key_path=private / 'key.pem',
        )

    def ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(self.ca_path))
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_cert_chain(certfile=str(self.cert_path), keyfile=str(self.key_path))
        return context
