import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json
from secret_guard import contains_secret_text

CLASSIFICATIONS = (
    'hard_requirement',
    'wish',
    'idea_opportunity',
    'decision',
    'action_item',
    'later_return',
    'informational_context',
)

ROUTES = {
    'hard_requirement': ['knowledge_base', 'roadmap'],
    'wish': ['wishlist'],
    'idea_opportunity': ['wishlist'],
    'decision': ['knowledge_base', 'roadmap'],
    'action_item': ['tasks'],
    'later_return': ['wishlist'],
    'informational_context': ['knowledge_base'],
}

_PATTERNS = (
    ('hard_requirement', (r'\bharde eis\b', r'\bmoet\b', r'\bvereist\b', r'\bmag niet\b')),
    ('decision', (r'\bbesloten\b', r'\bbesluit\b', r'\bwe kiezen\b', r'\bafgesproken\b')),
    ('action_item', (r'\bbouw\b', r'\bontwikkel\w*\b', r'\bmaak\b', r'\btest\b', r'\bimplementeer\w*\b', r'\bpas\b.*\baan\b')),
    ('wish', (r'\bik wil\b', r'\bwens\b', r'\bik zou graag\b')),
    ('idea_opportunity', (r'\bidee\b', r'\bkans\b', r'\bmisschien\b', r'\bkunnen we\b')),
    ('later_return', (r'\bkom .*later.* terug\b', r'\blater op terug\b', r'\bvoor later\b', r'\bvolgende keer\b')),
)
_DEVELOPMENT = (
    r'\bbouw\b',
    r'\bontwikkel\w*\b',
    r'\btest\b',
    r'\bimplementeer\w*\b',
    r'\bpas\b.*\baan\b',
)
_PROTECTED_ACTION = (
    r'\barchitectuurwijziging\b',
    r'\barchitecture change\b',
    r'\bproductie\b.*\b(installeer|installatie|deploy|plaats)\w*\b',
    r'\b(production|prod)\b.*\b(deploy|install)\w*\b',
)
_SOURCE_CHANNELS = {'chatgpt', 'nomad', 'speech'}
_SOURCE_ALIASES = {'spraak': 'speech', 'voice': 'speech'}


def _matches(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_intake(text, classification_hint=None):
    value = str(text or '').strip()
    if not value:
        raise ValueError('intake_text_required')
    if classification_hint is not None:
        hint = str(classification_hint).strip()
        if hint not in CLASSIFICATIONS:
            raise ValueError('invalid_classification_hint')
        classifications = [hint]
    else:
        classifications = [
            candidate for candidate, patterns in _PATTERNS
            if _matches(value, patterns)
        ]
        if not classifications:
            classifications = ['informational_context']
    return {
        'classification': classifications[0],
        'classifications': classifications,
        'development_context': _matches(value, _DEVELOPMENT),
        'approval_required': _matches(value, _PROTECTED_ACTION),
    }


def route_for_classification(classification):
    if classification not in ROUTES:
        raise ValueError('invalid_classification')
    return list(ROUTES[classification])


def route_for_classifications(classifications):
    routes = []
    for classification in classifications or []:
        for route in route_for_classification(classification):
            if route not in routes:
                routes.append(route)
    return routes


def _valid_store(data):
    return (
        isinstance(data, dict)
        and data.get('schema') == 1
        and isinstance(data.get('items', []), list)
        and all(
            isinstance(item, dict)
            and item.get('id')
            and item.get('fingerprint')
            and item.get('classification') in CLASSIFICATIONS
            for item in data.get('items', [])
        )
    )


def _normalize(text):
    return ' '.join(str(text or '').strip().lower().split())


def _fingerprint(source_channel, source_ref, text):
    source_ref = str(source_ref or '').strip()
    identity = (
        f'{source_channel}|{source_ref}'
        if source_ref
        else f'{source_channel}|{_normalize(text)}'
    )
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


class ConversationIntakeBridge:
    """Canonical conversation intake with selective derived routing.

    RuntimeV2/intake/items.json is the source of truth. Knowledge Base,
    roadmap-candidate and wishlist sections are derived projections only.
    """

    def __init__(self, path, task_store, document_sync, reports_root, opportunity_register=None, roadmap_regie=None):
        self.path = Path(path)
        self.tasks = task_store
        self.documents = document_sync
        self.reports_root = Path(reports_root)
        self.opportunities = opportunity_register
        self.roadmap = roadmap_regie

    def _load(self):
        return load_json(
            self.path,
            default={'schema': 1, 'items': []},
            recover_corrupt=True,
            validator=_valid_store,
        )

    def _save(self, data):
        atomic_write_json(self.path, data)

    @staticmethod
    def _validate(command):
        if not isinstance(command, dict):
            raise ValueError('intake_command_required')
        text = str(command.get('text') or '').strip()
        if not text:
            raise ValueError('intake_text_required')
        if contains_secret_text(text):
            raise ValueError('secret_like_content_rejected')

        source_channel = str(command.get('source_channel') or '').strip().lower()
        source_channel = _SOURCE_ALIASES.get(source_channel, source_channel)
        if not source_channel:
            raise ValueError('source_channel_required')
        if source_channel not in _SOURCE_CHANNELS:
            raise ValueError('invalid_source_channel')

        source_ref = str(command.get('source_ref') or '').strip()
        ingress_id = str(command.get('ingress_id') or '').strip()
        if not source_ref and not ingress_id:
            raise ValueError('source_ref_or_ingress_id_required')

        occurred_at = str(command.get('occurred_at') or '').strip()
        classified = classify_intake(text, command.get('classification_hint'))
        return {
            'text': text,
            'source_channel': source_channel,
            'source_ref': source_ref,
            'ingress_id': ingress_id,
            'occurred_at': occurred_at,
            **classified,
        }

    def accept(self, command):
        value = self._validate(command)
        fingerprint = _fingerprint(
            value['source_channel'], value['source_ref'], value['text']
        )
        data = self._load()
        item = next(
            (row for row in data['items'] if row.get('fingerprint') == fingerprint),
            None,
        )
        duplicate = item is not None

        if item is None:
            now = datetime.now(timezone.utc).isoformat()
            item = {
                'id': fingerprint[:24],
                'fingerprint': fingerprint,
                'text': value['text'],
                'source_channel': value['source_channel'],
                'source_ref': value['source_ref'],
                'ingress_id': value['ingress_id'],
                'occurred_at': value['occurred_at'] or now,
                'classification': value['classification'],
                'classifications': list(value['classifications']),
                'development_context': value['development_context'],
                'approval_required': value['approval_required'],
                'routes': route_for_classifications(value['classifications']),
                'route_results': {},
                'status': 'ACCEPTED',
                'created_at': now,
                'updated_at': now,
            }
            data['items'].append(item)
            self._save(data)

        follow_up_result = self._sync_follow_up(item)
        route_results = self._route(item)
        data = self._load()
        stored = next(
            row for row in data['items'] if row.get('fingerprint') == fingerprint
        )
        stored['route_results'] = route_results
        if follow_up_result is not None:
            stored['follow_up_result'] = follow_up_result
        stored['status'] = (
            'ROUTED'
            if all(result.get('ok') is True for result in route_results.values())
            else 'PARTIAL'
        )
        stored['updated_at'] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return {
            'id': stored['id'],
            'fingerprint': stored['fingerprint'],
            'classification': stored['classification'],
            'classifications': list(stored.get('classifications') or [stored['classification']]),
            'development_context': stored['development_context'],
            'approval_required': stored.get('approval_required') is True,
            'routes': list(stored['routes']),
            'route_results': dict(stored['route_results']),
            'status': stored['status'],
            'duplicate': duplicate,
        }

    def _sync_follow_up(self, item):
        if self.opportunities is None:
            return None
        classifications = item.get('classifications') or [item.get('classification')]
        relevant = [name for name in classifications if name in {'idea_opportunity', 'later_return'}]
        if not relevant:
            return None
        results = []
        for classification in relevant:
            category = 'conversation_opportunity' if classification == 'idea_opportunity' else 'follow_up'
            details = {
                'intake_id': item['id'],
                'source_channel': item.get('source_channel'),
                'source_ref': item.get('source_ref'),
                'classification': classification,
            }
            if classification == 'later_return':
                details['follow_up_policy'] = 'open_until_reviewed'
            opportunity_fingerprint = (
                f"intake:{item['fingerprint']}"
                if len(relevant) == 1
                else f"intake:{item['fingerprint']}:{classification}"
            )
            opportunity = self.opportunities.upsert(
                opportunity_fingerprint,
                category=category,
                subject=item.get('text', '')[:160],
                evidence=[f"{self.path}#{item['id']}"],
                details=details,
            )
            results.append({
                'ok': True,
                'classification': classification,
                'opportunity_id': opportunity.get('id'),
                'opportunity_fingerprint': opportunity.get('fingerprint'),
                'status': opportunity.get('status'),
                'proactive_decision': (opportunity.get('proactive_evaluation') or {}).get('decision'),
            })
        if len(results) == 1:
            return dict(results[0])
        return {'ok': all(row.get('ok') for row in results), 'items': results}

    def _route(self, item):
        results = {}
        for route in item.get('routes', []):
            try:
                if route == 'tasks':
                    task = self.tasks.capture(
                        item['text'][:160],
                        item['text'],
                        mode='DEVELOPMENT' if item.get('development_context') else 'USER',
                        priority=3,
                        intake_fingerprint=item['fingerprint'],
                        approval_required=item.get('approval_required') is True,
                    )
                    results[route] = {'ok': True, 'task_id': task['id']}
                elif route == 'roadmap':
                    roadmap_item = None
                    if self.roadmap is not None:
                        roadmap_item = self.roadmap.capture_intake(
                            item['text'],
                            mode='DEVELOPMENT' if item.get('development_context') else 'USER',
                            intake_fingerprint=item['fingerprint'],
                            approval_required=item.get('approval_required') is True,
                        )
                    projection = self._sync_projection(route)
                    results[route] = {
                        'ok': True,
                        **projection,
                        'roadmap_key': (roadmap_item or {}).get('key'),
                    }
                elif route in {'knowledge_base', 'wishlist'}:
                    result = self._sync_projection(route)
                    results[route] = {'ok': True, **result}
                else:
                    raise ValueError(f'unsupported_intake_route:{route}')
            except Exception as exc:
                results[route] = {
                    'ok': False,
                    'error': f'{type(exc).__name__}: {exc}',
                }
        return results

    def _sync_projection(self, route):
        knowledge_base = self.reports_root / 'KnowledgeBase'
        targets = {
            'knowledge_base': (
                knowledge_base / 'Knowledge_Base_Chat_Bronregister.md',
                'CONVERSATION_INTAKE',
            ),
            'roadmap': (
                knowledge_base / 'EnergieProject_Roadmap.md',
                'CONVERSATION_INTAKE_CANDIDATES',
            ),
            'wishlist': (
                knowledge_base / 'Wensenlijst.md',
                'CONVERSATION_INTAKE',
            ),
        }
        path, section = targets[route]
        items = [
            item for item in self._load()['items'] if route in item.get('routes', [])
        ]
        heading = {
            'knowledge_base': '## Projectmanager — Conversation Intake bronregister',
            'roadmap': '## Projectmanager — Conversation Intake roadmapkandidaten',
            'wishlist': '## Projectmanager — Wensenlijst uit Conversation Intake',
        }[route]
        lines = [
            heading,
            '- Canonieke bron: `Inbox/projectmanager_v2/RuntimeV2/intake/items.json`.',
            '- Deze sectie is een afgeleide projectie; RuntimeV2 blijft leidend.',
        ]
        for current in items:
            ref = (
                current.get('source_ref')
                or current.get('ingress_id')
                or current.get('id')
            )
            development = ' | development' if current.get('development_context') else ''
            lines.append(
                f"- [{'+'.join(current.get('classifications') or [current.get('classification')])}{development}] "
                f"{current.get('source_channel')}:{ref} — {current.get('text')}"
            )
        return self.documents.update(path, section, '\n'.join(lines), placement='top')

    def summary(self):
        items = self._load()['items']
        counts = {name: 0 for name in CLASSIFICATIONS}
        for item in items:
            classification = item.get('classification')
            if classification in counts:
                counts[classification] += 1
        return {
            'schema': 1,
            'canonical_path': str(self.path),
            'total': len(items),
            'classification_counts': counts,
            'latest': [
                {
                    'id': item.get('id'),
                    'classification': item.get('classification'),
                    'source_channel': item.get('source_channel'),
                    'source_ref': item.get('source_ref'),
                    'status': item.get('status'),
                }
                for item in items[-10:]
            ],
        }
