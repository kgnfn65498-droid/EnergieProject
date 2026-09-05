from __future__ import annotations

import hmac
import html
import io
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from docker_engine_tls_client import DockerEngineTlsClient
from nas_docker_tls import DEFAULT_PRIVATE_ROOT, DockerTlsConfig

_CSRF_TOKEN = secrets.token_urlsafe(32)
MAX_POST_BYTES = 16384
MAX_TLS_POST_BYTES = 2 * 1024 * 1024
MAX_TLS_CERT_BYTES = 512 * 1024
TLS_FILES = ('ca.pem', 'cert.pem', 'key.pem')
APPROVAL_SCHEMA = 'energie_pmv2_approval_ingress_v1'


def _runtime_root(project_root) -> Path:
    return Path(project_root) / 'Inbox' / 'projectmanager_v2' / 'RuntimeV2'


def _approval_root(project_root) -> Path:
    return Path(project_root) / 'Inbox' / 'projectmanager_v2' / 'ApprovalIngress'


def _read_pending(project_root) -> list[dict[str, Any]]:
    path = _runtime_root(project_root) / 'status' / 'current.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    return [
        item for item in data.get('decisions_needed', [])
        if isinstance(item, dict) and item.get('status') == 'PENDING' and item.get('id')
    ]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _tls_status(private_root: Path) -> dict[str, Any]:
    path = Path(private_root) / 'status.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'ready': False, 'host': ''}
    if not isinstance(data, dict):
        return {'ready': False, 'host': ''}
    return {
        'ready': data.get('ready') is True,
        'host': str(data.get('host') or '')[:255],
        'tested_at': str(data.get('tested_at') or '')[:100],
    }


def _atomic_private_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        path.chmod(mode)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _bundle_files(bundle: bytes) -> dict[str, bytes]:
    if not bundle or len(bundle) > MAX_TLS_POST_BYTES:
        raise ValueError('Docker-certificaatbundle ontbreekt of is te groot')
    found: dict[str, bytes] = {}
    try:
        archive = zipfile.ZipFile(io.BytesIO(bundle), 'r')
    except zipfile.BadZipFile as exc:
        raise ValueError('Docker-certificaatbundle is geen geldige ZIP') from exc
    with archive:
        for info in archive.infolist():
            member = Path(info.filename)
            if member.is_absolute() or '..' in member.parts or '\\' in info.filename:
                raise ValueError('Onveilig pad in Docker-certificaatbundle')
            if info.is_dir():
                continue
            base = member.name
            if base not in TLS_FILES:
                continue
            if base in found:
                raise ValueError(f'Dubbel certificaatbestand in bundle: {base}')
            if info.file_size <= 0 or info.file_size > MAX_TLS_CERT_BYTES:
                raise ValueError(f'Ongeldige certificaatgrootte: {base}')
            payload = archive.read(info)
            if len(payload) != info.file_size:
                raise ValueError(f'Certificaatbestand kon niet volledig worden gelezen: {base}')
            found[base] = payload
    missing = [name for name in TLS_FILES if name not in found]
    if missing:
        raise ValueError('Docker-certificaatbundle mist: ' + ', '.join(missing))
    return found


def install_nas_docker_tls_bundle(
    *,
    project_root: Path | str,
    private_root: Path | str = DEFAULT_PRIVATE_ROOT,
    host: str,
    bundle: bytes,
    client_cls=DockerEngineTlsClient,
) -> dict[str, Any]:
    """Validate a QNAP Docker certificate ZIP and install it only in private add-on data."""
    project = Path(project_root)
    private = Path(private_root)
    if _is_within(private, project):
        raise RuntimeError('Docker TLS-config mag nooit in het EnergieProject worden opgeslagen')
    files = _bundle_files(bundle)
    parent = private.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        parent.chmod(0o700)
    except OSError:
        pass
    stage = parent / f'.docker_tls_setup-{uuid4().hex}'
    backup = parent / f'.docker_tls_previous-{uuid4().hex}'
    stage.mkdir(mode=0o700)
    moved_old = False
    try:
        _atomic_private_bytes(stage / 'host.txt', (str(host or '').strip() + '\n').encode('utf-8'))
        for name in TLS_FILES:
            _atomic_private_bytes(stage / name, files[name])
        config = DockerTlsConfig.load(stage, project_root=project)
        ping = client_cls(config).ping()
        if ping.get('ok') is not True:
            raise RuntimeError('Docker TLS-ping gaf geen GREEN resultaat')
        status = {
            'ready': True,
            'host': config.host,
            'port': 2376,
            'tested_at': datetime.now(timezone.utc).isoformat(),
        }
        _atomic_private_bytes(
            stage / 'status.json',
            (json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'),
        )
        if private.exists():
            if private.is_symlink() or not private.is_dir():
                raise RuntimeError('Bestaande private Docker TLS-root is onveilig')
            os.replace(private, backup)
            moved_old = True
        os.replace(stage, private)
        if moved_old:
            shutil.rmtree(backup)
        return {'ready': True, 'host': config.host, 'port': 2376}
    except Exception:
        if moved_old and backup.exists() and not private.exists():
            try:
                os.replace(backup, private)
            except OSError:
                pass
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if backup.exists() and private.exists():
            shutil.rmtree(backup, ignore_errors=True)


def activate_projectmanager_connector(
    *,
    project_root: Path | str,
    private_root: Path | str = DEFAULT_PRIVATE_ROOT,
    client_cls=DockerEngineTlsClient,
) -> dict[str, Any]:
    """Restart exactly the filesystem MCP after explicit local GUI activation."""
    project = Path(project_root)
    private = Path(private_root)
    config = DockerTlsConfig.load(private, project_root=project)
    client = client_cls(config)
    if client.ping().get('ok') is not True:
        raise RuntimeError('Docker TLS-ping gaf geen GREEN resultaat')
    result = dict(client.reload_projectmanager_connector() or {})
    if result.get('ok') is not True or result.get('container') != 'energie-filesystem-mcp':
        raise RuntimeError('Projectmanager connector-activatie gaf geen veilig resultaat')
    status = _tls_status(private)
    status.update({
        'ready': True,
        'host': config.host,
        'port': 2376,
        'connector_activated_at': datetime.now(timezone.utc).isoformat(),
    })
    _atomic_private_bytes(
        private / 'status.json',
        (json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'),
    )
    return {'ok': True, 'container': 'energie-filesystem-mcp'}


def render_projectmanager_decisions(project_root) -> str:
    decisions = _read_pending(project_root)
    if not decisions:
        return ''
    cards = []
    for item in decisions[:10]:
        decision_id = html.escape(str(item.get('id')), quote=True)
        kind = html.escape(str(item.get('kind') or 'BESLISSING'))
        question = html.escape(str(item.get('question') or kind))
        cards.append(f'''<div style="border:1px solid #d0d0d0;border-radius:8px;padding:12px;margin:10px 0">
<strong>{kind}</strong><br>{question}
<form method="post" action="projectmanager-decision" style="display:inline-block;margin-top:8px">
<input type="hidden" name="csrf" value="{html.escape(_CSRF_TOKEN, quote=True)}">
<input type="hidden" name="decision_id" value="{decision_id}">
<input type="hidden" name="action" value="approve">
<button type="submit">Goedkeuren</button>
</form>
<form method="post" action="projectmanager-decision" style="display:inline-block;margin-top:8px;margin-left:8px">
<input type="hidden" name="csrf" value="{html.escape(_CSRF_TOKEN, quote=True)}">
<input type="hidden" name="decision_id" value="{decision_id}">
<input type="hidden" name="action" value="reject">
<button type="submit">Afwijzen</button>
</form>
</div>''')
    return ('<section id="pmv2-decisions" style="margin:16px 0;padding:14px;border:2px solid #d18b00;border-radius:10px">'
            '<h3>Projectmanager — beslissing nodig</h3>' + ''.join(cards) + '</section>')


def render_nas_container_cr_setup(project_root, *, private_root: Path | str = DEFAULT_PRIVATE_ROOT) -> str:
    del project_root
    status = _tls_status(Path(private_root))
    ready = status.get('ready') is True
    state = 'Gereed' if ready else 'Niet gereed'
    border = '#2e7d32' if ready else '#9a6700'
    host = html.escape(str(status.get('host') or ''), quote=True)
    return f'''<section id="pmv2-nas-container-cr" style="margin:16px 0;padding:14px;border:2px solid {border};border-radius:10px">
<h3>NAS Container Crash Recovery</h3>
<p><strong>{state}</strong> — veilige Docker TLS-koppeling via QNAP Container Station, poort 2376.</p>
<p>Eenmalige setup: open op de QNAP <strong>Container Station → Voorkeuren → Certificaten</strong>, activeer Docker-poort 2376 en download de Docker-certificaatbundle. Upload die bundle hier. Geen Terminal of sudo nodig.</p>
<form method="post" action="projectmanager-nas-cr-setup" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="{html.escape(_CSRF_TOKEN, quote=True)}">
<label>QNAP host/IP <input name="nas_host" value="{host}" required maxlength="255"></label><br>
<label>Docker-certificaatbundle <input type="file" name="certificate_bundle" accept=".zip,application/zip" required></label><br>
<button type="submit">Veilige koppeling testen en opslaan</button>
</form>
{(f'<form method="post" action="projectmanager-nas-cr-activate" style="margin-top:10px"><input type="hidden" name="csrf" value="{html.escape(_CSRF_TOKEN, quote=True)}"><button type="submit">Activeer ChatGPT-koppeling</button><span style="margin-left:8px;font-size:0.9em">herstart uitsluitend energie-filesystem-mcp éénmalig</span></form>' if ready else '')}
<p style="font-size:0.9em">Certificaten en privésleutel blijven uitsluitend in private Home Assistant add-ondata en worden nooit in het EnergieProject of in deze pagina teruggegeven.</p>
</section>'''


def inject_decision_card(page: bytes, card: str) -> bytes:
    if not card:
        return page
    marker = b'</body>'
    card_bytes = card.encode('utf-8')
    if marker in page:
        return page.replace(marker, card_bytes + b'\n' + marker, 1)
    return page + b'\n' + card_bytes


def _write_approval(project_root, *, decision_id: str, approved: bool) -> Path:
    root = _approval_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    ingress_id = uuid4().hex
    path = root / f'{ingress_id}.json'
    payload = {
        'schema': APPROVAL_SCHEMA,
        'id': ingress_id,
        'decision_id': decision_id,
        'approved': bool(approved),
        'approved_by': 'Peter',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source': 'home_assistant_ingress_ui',
    }
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o660)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return path


def _redirect(handler, notice='pm_decision_recorded'):
    handler.send_response(303)
    handler.send_header('Location', f'./?pm_notice={notice}')
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()


def _parse_multipart(raw: bytes, content_type: str) -> tuple[dict[str, str], dict[str, bytes]]:
    header = f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('utf-8')
    message = BytesParser(policy=policy.default).parsebytes(header + raw)
    if not message.is_multipart():
        raise ValueError('multipart_form_expected')
    fields: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != 'form-data':
            continue
        name = str(part.get_param('name', header='content-disposition') or '')
        if not name:
            continue
        payload = part.get_payload(decode=True) or b''
        filename = part.get_filename()
        if filename is not None:
            files[name] = payload
        else:
            fields[name] = payload.decode('utf-8', errors='strict')
    return fields, files


def install_projectmanager_web(
    app_module: Any,
    project_root: Path | str,
    *,
    private_root: Path | str = DEFAULT_PRIVATE_ROOT,
) -> None:
    """Install HA-ingress-only approval and NAS Container CR TLS setup UI."""
    root = Path(project_root)
    tls_private_root = Path(private_root)

    if not getattr(app_module, '_projectmanager_decision_html_installed', False):
        raw_html_page = app_module.html_page

        def wrapped_html_page(*args, **kwargs):
            page = raw_html_page(*args, **kwargs)
            card = (
                render_projectmanager_decisions(root)
                + render_nas_container_cr_setup(root, private_root=tls_private_root)
            )
            return inject_decision_card(page, card)

        app_module.html_page = wrapped_html_page
        app_module._projectmanager_decision_html_installed = True

    handler_cls = app_module.Handler
    if getattr(handler_cls, '_projectmanager_decision_post_installed', False):
        return
    raw_do_post = handler_cls.do_POST

    def wrapped_do_post(self):
        parsed_path = urlparse(self.path).path.rstrip('/')
        is_decision = parsed_path == '/projectmanager-decision' or parsed_path.endswith('/projectmanager-decision')
        is_tls_setup = parsed_path == '/projectmanager-nas-cr-setup' or parsed_path.endswith('/projectmanager-nas-cr-setup')
        is_connector_activate = parsed_path == '/projectmanager-nas-cr-activate' or parsed_path.endswith('/projectmanager-nas-cr-activate')
        if not (is_decision or is_tls_setup or is_connector_activate):
            return raw_do_post(self)

        if is_tls_setup:
            try:
                length = int(self.headers.get('Content-Length', '0') or 0)
                if length <= 0 or length > MAX_TLS_POST_BYTES:
                    raise ValueError('invalid_content_length')
                content_type = str(self.headers.get('Content-Type', ''))
                if 'multipart/form-data' not in content_type.lower():
                    raise ValueError('unsupported_content_type')
                fields, files = _parse_multipart(self.rfile.read(length), content_type)
                csrf = str(fields.get('csrf') or '')
                if not hmac.compare_digest(csrf, _CSRF_TOKEN):
                    raise PermissionError('csrf_validation_failed')
                host = str(fields.get('nas_host') or '').strip()
                bundle = files.get('certificate_bundle') or b''
                install_nas_docker_tls_bundle(
                    project_root=root,
                    private_root=tls_private_root,
                    host=host,
                    bundle=bundle,
                )
                _redirect(self, 'nas_cr_tls_ready')
            except Exception:
                _redirect(self, 'nas_cr_tls_rejected')
            return

        if is_connector_activate:
            try:
                length = int(self.headers.get('Content-Length', '0') or 0)
                if length <= 0 or length > MAX_POST_BYTES:
                    raise ValueError('invalid_content_length')
                content_type = str(self.headers.get('Content-Type', '')).lower()
                if 'application/x-www-form-urlencoded' not in content_type:
                    raise ValueError('unsupported_content_type')
                form = parse_qs(self.rfile.read(length).decode('utf-8', errors='strict'))
                csrf = str((form.get('csrf') or [''])[0])
                if not hmac.compare_digest(csrf, _CSRF_TOKEN):
                    raise PermissionError('csrf_validation_failed')
                activate_projectmanager_connector(project_root=root, private_root=tls_private_root)
                _redirect(self, 'nas_cr_connector_activated')
            except Exception:
                _redirect(self, 'nas_cr_connector_activation_failed')
            return

        try:
            length = int(self.headers.get('Content-Length', '0') or 0)
            if length <= 0 or length > MAX_POST_BYTES:
                raise ValueError('invalid_content_length')
            content_type = str(self.headers.get('Content-Type', '')).lower()
            if 'application/x-www-form-urlencoded' not in content_type:
                raise ValueError('unsupported_content_type')
            form = parse_qs(self.rfile.read(length).decode('utf-8', errors='strict'))
            csrf = str((form.get('csrf') or [''])[0])
            if not hmac.compare_digest(csrf, _CSRF_TOKEN):
                raise PermissionError('csrf_validation_failed')
            decision_id = str((form.get('decision_id') or [''])[0]).strip()
            action = str((form.get('action') or [''])[0]).strip().lower()
            if action not in {'approve', 'reject'}:
                raise ValueError('invalid_action')
            pending_ids = {str(item.get('id')) for item in _read_pending(root)}
            if decision_id not in pending_ids:
                raise ValueError('decision_not_pending')
            _write_approval(root, decision_id=decision_id, approved=action == 'approve')
            _redirect(self)
        except Exception:
            _redirect(self, 'pm_decision_rejected')

    handler_cls.do_POST = wrapped_do_post
    handler_cls._projectmanager_decision_post_installed = True
