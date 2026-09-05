from __future__ import annotations

import hmac
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

_CSRF_TOKEN = secrets.token_urlsafe(32)
MAX_POST_BYTES = 16384
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


def install_projectmanager_web(app_module: Any, project_root: Path | str) -> None:
    """Install HA-ingress-only approval UI without mutating RuntimeV2 directly."""
    root = Path(project_root)

    if not getattr(app_module, '_projectmanager_decision_html_installed', False):
        raw_html_page = app_module.html_page

        def wrapped_html_page(*args, **kwargs):
            page = raw_html_page(*args, **kwargs)
            return inject_decision_card(page, render_projectmanager_decisions(root))

        app_module.html_page = wrapped_html_page
        app_module._projectmanager_decision_html_installed = True

    handler_cls = app_module.Handler
    if getattr(handler_cls, '_projectmanager_decision_post_installed', False):
        return
    raw_do_post = handler_cls.do_POST

    def wrapped_do_post(self):
        parsed_path = urlparse(self.path).path.rstrip('/')
        if not (parsed_path == '/projectmanager-decision' or parsed_path.endswith('/projectmanager-decision')):
            return raw_do_post(self)
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
