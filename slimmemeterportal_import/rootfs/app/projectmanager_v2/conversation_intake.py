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
    ('action_item', (
        r'\bbouw\b', r'\bontwikkel\w*\b', r'\bmaak\b', r'\btest\b',
        r'\bimplementeer\w*\b', r'\bpas\b.*\baan\b', r'\binstalleer\w*\b',
        r'\bdeploy\w*\b', r'\bplaats\w*\b',
    )),
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
    r'\bwijzig\w*\b',
    r'\bverander\w*\b',
    r'\bherstructureer\w*\b',
    r'\bherontwerp\w*\b',
    r'\binstalleer\w*\b',
    r'\bdeploy\w*\b',
    r'\bplaats\w*\b',
    r'\bactiveer\w*\b',
    r'\bpubliceer\w*\b',
    r'\bzet\b.*\blive\b',
)
_ARCHITECTURE_CONTEXT = (
    r'\barchitectuur\w*\b',
    r'\bsysteemarchitectuur\w*\b',
    r'\barchitecture\b',
    r'\bopzet\b',
    r'\bsysteemstructuur\b',
    r'\bsysteemopzet\b',
    r'\bsysteem\b',
)
_ARCHITECTURE_ACTION = (
    r'\bpas\b.*\baan\b',
    r'\bwijzig\w*\b',
    r'\bverander\w*\b',
    r'\bherstructureer\w*\b',
    r'\bherontwerp\w*\b',
    r'\bbouw\b',
    r'\bmaak\b.*\bgeschikt\b',
    r'\bvoeg\b.*\btoe\b',
    r'\bintegreer\w*\b',
    r'\bkoppel\w*\b',
)
_PRODUCTION_CONTEXT = (
    r'\bproductie\b', r'\bproductieplaatsing\b', r'\bproduction\b', r'\bprod\b',
    r'\bhome[ -]?assistant\b', r'\bHA\b', r'\bhome[ -]?assistant[ -]?green\b', r'\bgreen\b',
)
_PRODUCTION_ACTION = (
    r'\binstalleer\w*\b', r'\binstallatie\w*\b', r'\bdeploy\w*\b',
    r'\bplaats\w*\b', r'\buitrol\w*\b', r'\brol\b.*\buit\b',
    r'\bactiveer\w*\b', r'\bactief\b', r'\bpubliceer\w*\b',
    r'\bzet\b', r'\bvoer\b.*\bdoor\b', r'\bbreng\b.*\blive\b',
)
_LIVE_ACTION = (r'\bzet\b.*\blive\b', r'\bbreng\b.*\blive\b', r'\bgo[ -]?live\b')
_SOURCE_CHANNELS = {'chatgpt', 'typed', 'dictation', 'voice', 'nomad', 'speech'}
_SOURCE_ALIASES = {'spraak': 'speech', 'typed/chatgpt': 'chatgpt'}
_SPEECH_CHANNELS = {'dictation', 'voice', 'nomad', 'speech'}
_RECENT_TRANSCRIPT_DEDUPE_SECONDS = 8
_TRANSCRIPT_UNCERTAIN_BELOW = 0.70


def _matches(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def protected_action_kind(text):
    value = str(text or '')
    architecture_change = _matches(value, _ARCHITECTURE_CONTEXT) and _matches(value, _ARCHITECTURE_ACTION)
    if architecture_change:
        return 'architecture_change'
    if _matches(value, _LIVE_ACTION):
        return 'production_deploy'
    if _matches(value, _PRODUCTION_CONTEXT) and _matches(value, _PRODUCTION_ACTION):
        return 'production_deploy'
    return None


def _protected_action(text):
    return protected_action_kind(text) is not None


def is_new_chat_intent(text):
    value = _normalize(text)
    if not value:
        return False
    patterns = (
        r'\bnieuwe chat\b',
        r'\bverse chat\b',
        r'\bga verder\b.*\bchat\b',
        r'\bzet over\b.*\bchat\b',
        r'\bbereid\b.*\bchat\b.*\bvoor\b',
        r'\bvolgende build\b.*\bchat\b',
    )
    return _matches(value, patterns)


def _parse_timestamp(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


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
        'approval_required': _protected_action(value),
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
        transcript_id = str(command.get('transcript_id') or '').strip()
        confidence_raw = command.get('transcript_confidence')
        transcript_confidence = None
        if confidence_raw not in (None, ''):
            try:
                transcript_confidence = float(confidence_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError('invalid_transcript_confidence') from exc
            if not 0.0 <= transcript_confidence <= 1.0:
                raise ValueError('invalid_transcript_confidence')
        transcript_uncertain = bool(
            source_channel in _SPEECH_CHANNELS
            and transcript_confidence is not None
            and transcript_confidence < _TRANSCRIPT_UNCERTAIN_BELOW
        )
        classified = classify_intake(text, command.get('classification_hint'))
        return {
            'text': text,
            'source_channel': source_channel,
            'canonical_source_channel': 'speech' if source_channel in _SPEECH_CHANNELS else source_channel,
            'source_ref': source_ref,
            'ingress_id': ingress_id,
            'occurred_at': occurred_at,
            'transcript_id': transcript_id,
            'transcript_confidence': transcript_confidence,
            'transcript_uncertain': transcript_uncertain,
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
        duplicate_reason = 'event_id' if item is not None else None
        if item is None and value['source_channel'] in _SPEECH_CHANNELS:
            current_at = _parse_timestamp(value.get('occurred_at')) or datetime.now(timezone.utc)
            normalized = _normalize(value['text'])
            for row in reversed(data['items']):
                if row.get('source_channel') not in _SPEECH_CHANNELS:
                    continue
                if _normalize(row.get('text')) != normalized:
                    continue
                previous_at = _parse_timestamp(row.get('occurred_at') or row.get('created_at'))
                if previous_at is None:
                    continue
                if abs((current_at - previous_at).total_seconds()) <= _RECENT_TRANSCRIPT_DEDUPE_SECONDS:
                    item = row
                    fingerprint = str(row.get('fingerprint') or fingerprint)
                    duplicate_reason = 'recent_exact_transcript'
                    break
        duplicate = item is not None

        if item is None:
            now = datetime.now(timezone.utc).isoformat()
            item = {
                'id': fingerprint[:24],
                'fingerprint': fingerprint,
                'text': value['text'],
                'source_channel': value['source_channel'],
                'canonical_source_channel': value['canonical_source_channel'],
                'source_ref': value['source_ref'],
                'ingress_id': value['ingress_id'],
                'occurred_at': value['occurred_at'] or now,
                'transcript_id': value['transcript_id'],
                'transcript_confidence': value['transcript_confidence'],
                'transcript_uncertain': value['transcript_uncertain'],
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
            'duplicate_reason': duplicate_reason,
            'source_channel': stored.get('source_channel'),
            'canonical_source_channel': stored.get('canonical_source_channel', stored.get('source_channel')),
            'transcript_uncertain': stored.get('transcript_uncertain') is True,
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
                'source_channel': item.get('canonical_source_channel', item.get('source_channel')),
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
            classifications = item.get('classifications') or [item.get('classification')]
            for classification in dict.fromkeys(classifications):
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
                    'source_channel': item.get('canonical_source_channel', item.get('source_channel')),
                    'source_ref': item.get('source_ref'),
                    'status': item.get('status'),
                }
                for item in items[-10:]
            ],
        }
