from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, atomic_write_text, load_json
from secret_guard import contains_secret_text, redact


_SCHEMA = 'energie_projectmanager_handover_snapshot_v1'
_ACTIVE_ROADMAP = {'ACTIVE', 'BLOCKED', 'IN_PROGRESS'}
_OPEN_ROADMAP = {'OPEN', 'READY', 'PLANNED'}
_ACTIVE_TASKS = {'ACTIVE', 'BLOCKED', 'WAITING_APPROVAL', 'PAUSED', 'IN_PROGRESS'}
_OPEN_HANDOFFS = {'OPEN', 'ACTIVE', 'PENDING', 'BLOCKED'}
_OPEN_ISSUES = {'OPEN'}
_PENDING_APPROVALS = {'PENDING', 'WAITING_APPROVAL'}
_BINDING_CLASSIFICATIONS = {'hard_requirement', 'decision'}


def _utc_now(now=None):
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _compact_item(item: dict, keys) -> dict:
    return {key: item.get(key) for key in keys if key in item}


class HandoverSnapshotService:
    """Builds durable continuation snapshots from canonical PM runtime state.

    The JSON `ready/current.json` pointer is authoritative. History is append-only
    and is used as the fail-safe source when that pointer is incomplete/corrupt.
    """

    def __init__(self, runtime_root, *, project_root=None, issues=None, audit=None):
        self.runtime_root = Path(runtime_root)
        self.project_root = Path(project_root) if project_root is not None else None
        self.issues = issues
        self.audit = audit
        self.handover_root = self.runtime_root / 'handover'
        self.history_root = self.handover_root / 'history'
        self.ready_root = self.handover_root / 'ready'

    def _load_required_dict(self, relative: str) -> dict:
        path = self.runtime_root / relative
        try:
            value = load_json(path, default=None)
        except Exception as exc:
            self._record_failure('canonical_state_unreadable', f'{relative}: {type(exc).__name__}: {exc}')
            raise RuntimeError(f'cannot build handover: unreadable canonical state {relative}') from exc
        if not isinstance(value, dict):
            self._record_failure('canonical_state_invalid', f'{relative}: expected object')
            raise RuntimeError(f'cannot build handover: invalid canonical state {relative}')
        return value

    def _load_optional_dict(self, relative: str) -> dict:
        path = self.runtime_root / relative
        try:
            value = load_json(path, default={})
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def _read_text_candidates(self, candidates) -> str:
        if self.project_root is None:
            return ''
        for relative in candidates:
            path = self.project_root / relative
            try:
                if path.is_file():
                    value = path.read_text(encoding='utf-8').strip()
                    if value:
                        return value
            except OSError:
                continue
        return ''

    def _project_release_version(self) -> str:
        return self._read_text_candidates(('App/VERSIE.txt', 'VERSIE.txt'))

    def _pm_version(self) -> str:
        return self._read_text_candidates((
            'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt',
            'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt',
        ))

    def _valid_status(self, status: dict) -> bool:
        release = status.get('release')
        progress = status.get('progress')
        return (
            status.get('schema') == 'energie_projectmanager_status_v2'
            and isinstance(status.get('mode'), str) and bool(status.get('mode'))
            and isinstance(release, dict) and bool(release.get('version'))
            and isinstance(progress, dict)
            and isinstance(status.get('release_chain'), dict)
        )

    def _snapshot_valid(self, snapshot) -> bool:
        if not isinstance(snapshot, dict):
            return False
        if snapshot.get('schema') != _SCHEMA or snapshot.get('status') != 'ready':
            return False
        required_strings = ('handover_id', 'created_at', 'release_version', 'pm_version', 'mode')
        if any(not isinstance(snapshot.get(key), str) or not snapshot.get(key) for key in required_strings):
            return False
        if not isinstance(snapshot.get('progress'), dict):
            return False
        if not isinstance(snapshot.get('release_truth'), dict):
            return False
        if not isinstance(snapshot.get('source'), dict):
            return False
        return True

    def _record_failure(self, fingerprint: str, detail: str) -> None:
        if self.issues is not None:
            try:
                self.issues.open(
                    f'handover:{fingerprint}', severity='ORANGE',
                    title='Automatische nieuwe-chat-overdracht mislukt',
                    details={'detail': str(detail)},
                )
            except Exception:
                pass
        if self.audit is not None:
            try:
                self.audit.write('handover.snapshot.failed', {'fingerprint': fingerprint, 'detail': str(detail)})
            except Exception:
                pass

    def _binding_context(self, intake: dict) -> list[dict]:
        result = []
        for item in intake.get('items', []) if isinstance(intake.get('items'), list) else []:
            if not isinstance(item, dict):
                continue
            classes = item.get('classifications') or [item.get('classification')]
            if not any(value in _BINDING_CLASSIFICATIONS for value in classes):
                continue
            text = str(item.get('text') or '').strip()
            if not text or contains_secret_text(text):
                continue
            result.append(_compact_item(item, (
                'id', 'classification', 'classifications', 'text', 'source_channel', 'created_at'
            )))
        result.sort(key=lambda value: str(value.get('created_at') or ''))
        return result[-20:]

    def _roadmap_summary(self, roadmap: dict) -> dict:
        items = roadmap.get('items', []) if isinstance(roadmap.get('items'), list) else []
        safe_items = [item for item in items if isinstance(item, dict)]
        active = [item for item in safe_items if str(item.get('status', '')).upper() in _ACTIVE_ROADMAP]
        nxt = [item for item in safe_items if str(item.get('status', '')).upper() in _OPEN_ROADMAP]

        def key(item):
            return (
                int(item.get('priority', 999999)) if str(item.get('priority', '')).isdigit() else 999999,
                int(item.get('canonical_order', 999999)) if str(item.get('canonical_order', '')).isdigit() else 999999,
                str(item.get('key') or ''),
            )

        active.sort(key=key)
        nxt.sort(key=key)
        fields = ('key', 'title', 'status', 'priority', 'mode', 'executor', 'canonical_order')
        return {
            'canonical': redact(roadmap.get('canonical', {})) if isinstance(roadmap.get('canonical'), dict) else {},
            'active': [_compact_item(item, fields) for item in active[:10]],
            'next': [_compact_item(item, fields) for item in nxt[:10]],
        }

    def _select_items(self, payload: dict, statuses: set[str], *, max_items=20) -> list[dict]:
        items = payload.get('items', []) if isinstance(payload.get('items'), list) else []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get('status', '')).upper()
            if status in statuses:
                result.append(redact(item))
        return result[:max_items]

    def _build_markdown(self, snapshot: dict) -> str:
        progress = snapshot.get('progress', {})
        lines = [
            f"# Handover {snapshot['handover_id']}",
            '',
            f"- Status: {snapshot['status']}",
            f"- Aangemaakt: {snapshot['created_at']}",
            f"- Bron: {snapshot['source'].get('channel', '')}",
            f"- Release: {snapshot['release_version']}",
            f"- Projectmanager: {snapshot['pm_version']}",
            f"- Modus: {snapshot['mode']}",
            f"- Voortgang: {progress.get('step_label', '')} ({progress.get('percentage', '')}%)",
            f"- Volgende stap: {snapshot.get('next_step', '')}",
            '',
        ]
        if snapshot.get('blockers'):
            lines += ['## Blockers'] + [f"- {value}" for value in snapshot['blockers']] + ['']
        if snapshot.get('roadmap', {}).get('active'):
            lines += ['## Actieve roadmap'] + [
                f"- {item.get('key', '')}: {item.get('title', '')} [{item.get('status', '')}]"
                for item in snapshot['roadmap']['active']
            ] + ['']
        if snapshot.get('roadmap', {}).get('next'):
            lines += ['## Hierna'] + [
                f"- {item.get('key', '')}: {item.get('title', '')} [{item.get('status', '')}]"
                for item in snapshot['roadmap']['next']
            ] + ['']
        if snapshot.get('open_approvals'):
            lines += ['## Open approvals'] + [
                f"- {item.get('kind', item.get('id', 'approval'))}: {item.get('status', '')}"
                for item in snapshot['open_approvals']
            ] + ['']
        if snapshot.get('open_issues'):
            lines += ['## Open issues'] + [
                f"- {item.get('fingerprint', item.get('id', 'issue'))}: {item.get('severity', '')}"
                for item in snapshot['open_issues']
            ] + ['']
        if snapshot.get('binding_context'):
            lines += ['## Bindende context'] + [f"- {item.get('text', '')}" for item in snapshot['binding_context']] + ['']
        lines += [
            '## Hervatten',
            f"Ga verder met: {snapshot.get('next_step', '')}",
            '',
        ]
        return '\n'.join(lines)

    def latest_ready(self):
        current = self.ready_root / 'current.json'
        try:
            value = load_json(current, default=None)
        except Exception:
            value = None
        if self._snapshot_valid(value):
            return value

        if self.history_root.is_dir():
            # Filenames start with UTC timestamp, so lexicographic reverse is latest-first.
            for path in sorted(self.history_root.glob('*.json'), reverse=True):
                try:
                    value = load_json(path, default=None)
                except Exception:
                    continue
                if self._snapshot_valid(value):
                    return value
        return None

    def resume_context(self):
        return self.latest_ready()

    def create(self, *, source_channel: str, trigger_text: str, trigger_id: str = '', now=None) -> dict:
        source_channel = str(source_channel or '').strip() or 'chatgpt'
        trigger_id = str(trigger_id or '').strip()
        trigger_text = str(trigger_text or '').strip()

        # Event-id idempotence happens before reading the mutable status. A retried
        # delivery of an already completed handover must never create a second snapshot.
        existing = self.latest_ready()
        if (
            existing and trigger_id
            and existing.get('source', {}).get('trigger_id') == trigger_id
            and existing.get('source', {}).get('channel') == source_channel
        ):
            return existing

        status = self._load_required_dict('status/current.json')
        if not self._valid_status(status):
            self._record_failure('canonical_status_invalid', 'status/current.json failed handover validation')
            raise RuntimeError('cannot build handover: canonical status is incomplete or invalid')

        release_version = str(status.get('release', {}).get('version') or '').strip()
        project_release = self._project_release_version()
        if project_release and project_release != release_version:
            self._record_failure('release_identity_mismatch', f'status={release_version}, project={project_release}')
            raise RuntimeError('cannot build handover: release identity mismatch')

        pm_version = self._pm_version()
        if not pm_version:
            # Runtime status historically did not expose PM identity. Fail closed instead
            # of fabricating it when a project tree was supplied.
            if self.project_root is not None:
                self._record_failure('pm_identity_missing', 'Projectmanager VERSION.txt missing')
                raise RuntimeError('cannot build handover: Projectmanager version missing')
            pm_version = str(status.get('projectmanager_version') or 'unknown')

        roadmap = self._load_optional_dict('roadmap/queue.json')
        tasks = self._load_optional_dict('state/tasks.json')
        decisions = self._load_optional_dict('decisions/queue.json')
        issues = self._load_optional_dict('issues/issues.json')
        handoffs = self._load_optional_dict('handoffs/queue.json')
        intake = self._load_optional_dict('intake/items.json')
        self_audit = self._load_optional_dict('self_audit/current.json')
        runtime_snapshot = self._load_optional_dict('snapshots/current_runtime.json')

        progress = redact(status.get('progress', {}))
        blockers = progress.get('blockers') if isinstance(progress.get('blockers'), list) else []
        if not blockers:
            active_task = status.get('active_task', {}) if isinstance(status.get('active_task'), dict) else {}
            blockers = active_task.get('blockers', []) if isinstance(active_task.get('blockers'), list) else []

        status_approvals = status.get('decisions_needed', []) if isinstance(status.get('decisions_needed'), list) else []
        open_approvals = [redact(item) for item in status_approvals if isinstance(item, dict) and str(item.get('status', 'PENDING')).upper() in _PENDING_APPROVALS]
        if not open_approvals:
            open_approvals = self._select_items(decisions, _PENDING_APPROVALS)

        status_issues = status.get('open_issues', []) if isinstance(status.get('open_issues'), list) else []
        open_issues = [redact(item) for item in status_issues if isinstance(item, dict) and str(item.get('status', 'OPEN')).upper() in _OPEN_ISSUES]
        if not open_issues:
            open_issues = self._select_items(issues, _OPEN_ISSUES)

        status_handoffs = status.get('handoffs', []) if isinstance(status.get('handoffs'), list) else []
        active_handoffs = [redact(item) for item in status_handoffs if isinstance(item, dict) and str(item.get('status', 'OPEN')).upper() in _OPEN_HANDOFFS]
        if not active_handoffs:
            active_handoffs = self._select_items(handoffs, _OPEN_HANDOFFS)

        release_truth = {
            'release': redact(status.get('release', {})),
            'release_chain': redact(status.get('release_chain', {})),
        }
        test_evidence = {
            'self_audit': redact(self_audit),
            'runtime_checks': redact(runtime_snapshot.get('checks', [])) if isinstance(runtime_snapshot.get('checks'), list) else [],
            'observed_at': runtime_snapshot.get('observed_at'),
        }

        created = _utc_now(now)
        handover_id = uuid4().hex
        source_text = '[REDACTED]' if contains_secret_text(trigger_text) else trigger_text
        roadmap_summary = self._roadmap_summary(roadmap)
        active_tasks = self._select_items(tasks, _ACTIVE_TASKS)
        unfinished = []
        unfinished.extend([{'kind': 'blocker', 'text': value} for value in blockers if str(value).strip()])
        unfinished.extend([{'kind': 'roadmap', **item} for item in roadmap_summary.get('active', [])])
        unfinished.extend([{'kind': 'issue', 'id': item.get('id'), 'fingerprint': item.get('fingerprint'), 'severity': item.get('severity')} for item in open_issues])

        snapshot = {
            'schema': _SCHEMA,
            'status': 'ready',
            'handover_id': handover_id,
            'created_at': created.isoformat(),
            'source': {
                'channel': source_channel,
                'trigger_id': trigger_id,
                'trigger_text': source_text,
            },
            'release_version': release_version,
            'pm_version': pm_version,
            'mode': str(status.get('mode')),
            'roadmap': roadmap_summary,
            'progress': progress,
            'next_step': str(status.get('next_action') or progress.get('next_action') or status.get('active_task', {}).get('next_action') or ''),
            'blockers': redact(list(blockers)),
            'active_tasks': active_tasks,
            'open_approvals': open_approvals[:20],
            'active_handoffs': active_handoffs[:20],
            'open_issues': open_issues[:20],
            'binding_context': self._binding_context(intake),
            'release_truth': release_truth,
            'test_evidence': test_evidence,
            'unfinished': unfinished[:40],
        }
        snapshot = redact(snapshot)
        if not self._snapshot_valid(snapshot):
            self._record_failure('snapshot_validation_failed', 'assembled snapshot failed validation')
            raise RuntimeError('cannot build handover: assembled snapshot is invalid')

        encoded = json.dumps(snapshot, ensure_ascii=False)
        if len(encoded.encode('utf-8')) >= 100_000:
            self._record_failure('snapshot_too_large', f'{len(encoded.encode("utf-8"))} bytes')
            raise RuntimeError('cannot build handover: snapshot exceeds compact-size limit')

        stamp = created.strftime('%Y%m%dT%H%M%S%fZ')
        stem = f'{stamp}-{handover_id}'
        history_json = self.history_root / f'{stem}.json'
        history_md = self.history_root / f'{stem}.md'
        markdown = self._build_markdown(snapshot)

        # History is complete before the ready pointer changes. current.json is written
        # last and is the authoritative atomic publication of a new handover.
        atomic_write_json(history_json, snapshot)
        atomic_write_text(history_md, markdown)
        atomic_write_text(self.ready_root / 'current.md', markdown)
        atomic_write_json(self.ready_root / 'current.json', snapshot)

        if self.audit is not None:
            try:
                self.audit.write('handover.snapshot.ready', {
                    'handover_id': handover_id,
                    'source_channel': source_channel,
                    'release_version': release_version,
                    'pm_version': pm_version,
                })
            except Exception:
                pass
        return snapshot
