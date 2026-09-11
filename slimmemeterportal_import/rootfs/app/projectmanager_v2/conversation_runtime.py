from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from conversation_intake import is_new_chat_intent, protected_action_kind
from persistence import atomic_write_json, load_json
from secret_guard import contains_secret_text


_SPEECH_CHANNELS = {'voice', 'speech', 'dictation', 'nomad'}
_CONFIRM_PATTERNS = (
    r'^\s*ja\s*,?\s*voer\s+(?:het\s+)?uit[.!]?\s*$',
    r'^\s*ja\s*,?\s*definitief\s+(?:uitvoeren|doen)[.!]?\s*$',
    r'^\s*voer\s+(?:het\s+)?definitief\s+uit[.!]?\s*$',
)
_STATUS_PATTERNS = (
    r'\bhoe staat\b', r'\bstatus\b', r'\bvoortgang\b', r'\bstap\b.*\bvan\b',
    r'\bstap\s+\d+\s*/\s*\d+\b', r'\bblocker\w*\b.*\b(?:wat|welke|status|uitleg)\b',
    r'\broadmap\b.*\b(?:status|waar|wat|volgende)\b', r'\breleaseketen\b',
    r'\bwatcher\b.*\bstatus\b', r'\brollback\b.*\bstatus\b',
)
_ROADMAP_OR_TASK_QUERY = re.compile(r'\b(?:roadmap|taak|taken|action[ -]?item)\b', re.IGNORECASE)
_KB_QUERY = re.compile(r'\b(?:knowledge base|kennisbank)\b', re.IGNORECASE)
_DEICTIC_BLOCKER = re.compile(r'\b(?:die|deze)\s+blocker\b', re.IGNORECASE)
_VERSION = re.compile(r'\b\d+\.\d+(?:\.\d+)?\b')

_PM_INTENT_PATTERNS = (
    r'\bprojectmanager\b', r'\broadmap\b', r'\bknowledge base\b', r'\bkennisbank\b',
    r'\bblocker\w*\b', r'\bhandover\b', r'\boverdracht\b', r'\bnieuwe chat\b', r'\bverse chat\b',
    r'\b(?:release|build|versie)\s*\d+\.\d+(?:\.\d+)?\b',
    r'\bv?\d+(?:\.\d+){0,2}\b.*\b(?:status|installeer|deploy|live|audit|test|bouw|maak|draait|running|actief)\b',
    r'\b(?:installeer|deploy|breng|zet|rol)\b.*\b(?:home[ -]?assistant|green|productie|live)\b',
    r'\b(?:architectuur|systeemarchitectuur)\b', r'\bclaude cowork\b',
    r'\bstap\s+\d+\s*/\s*\d+\b',
)


def _matches(text: str, patterns) -> bool:
    return any(re.search(pattern, text or '', flags=re.IGNORECASE) for pattern in patterns)


def _explicit_confirmation(text: str) -> bool:
    return _matches(text, _CONFIRM_PATTERNS)


def _safe_confidence(value):
    if value in (None, ''):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0.0 <= parsed <= 1.0 else None


def _event_key(source_channel: str, turn_id: str) -> str:
    return hashlib.sha256(f'{source_channel}|{turn_id}'.encode('utf-8')).hexdigest()


class ProjectmanagerConversationRuntime:
    """One conversational front door for typed, dictation, Voice and Nomad.

    It does not own separate PM truth. Reads come from status/current.json and
    mutations flow through ConversationIntakeBridge / canonical DecisionQueue.
    """

    def __init__(self, runtime_root, *, intake, approval, handover, audit=None, reports_root=None):
        self.root = Path(runtime_root)
        self.intake = intake
        self.approval = approval
        self.handover = handover
        self.audit = audit
        self.reports_root = Path(reports_root) if reports_root is not None else None
        self.context_path = self.root / 'conversation' / 'context.json'
        self.results_path = self.root / 'conversation' / 'results.json'

    @staticmethod
    def handles(text: str) -> bool:
        value = str(text or '').strip()
        return bool(value) and (is_new_chat_intent(value) or protected_action_kind(value) is not None or _matches(value, _PM_INTENT_PATTERNS))

    def _load_status(self) -> dict:
        try:
            status = load_json(self.root / 'status' / 'current.json', default=None)
        except Exception as exc:
            raise RuntimeError('canonical_projectmanager_status_unreadable') from exc
        if not isinstance(status, dict) or status.get('schema') != 'energie_projectmanager_status_v2':
            raise RuntimeError('canonical_projectmanager_status_invalid')
        return status

    def _load_contexts(self) -> dict:
        value = load_json(self.context_path, default={'schema': 1, 'sessions': {}}, recover_corrupt=True)
        if not isinstance(value, dict) or not isinstance(value.get('sessions', {}), dict):
            return {'schema': 1, 'sessions': {}}
        return value

    def _session(self, session_id: str) -> dict:
        return dict(self._load_contexts().get('sessions', {}).get(session_id, {}))

    def _update_session(self, session_id: str, **updates) -> None:
        data = self._load_contexts()
        session = dict(data.setdefault('sessions', {}).get(session_id, {}))
        session.update(updates)
        session['updated_at'] = datetime.now(timezone.utc).isoformat()
        data['sessions'][session_id] = session
        # Prevent unbounded conversation-state growth.
        if len(data['sessions']) > 100:
            ordered = sorted(data['sessions'].items(), key=lambda pair: str(pair[1].get('updated_at') or ''))
            data['sessions'] = dict(ordered[-100:])
        atomic_write_json(self.context_path, data)

    def _load_results(self) -> dict:
        value = load_json(self.results_path, default={'schema': 1, 'items': []}, recover_corrupt=True)
        if not isinstance(value, dict) or not isinstance(value.get('items', []), list):
            return {'schema': 1, 'items': []}
        return value

    def _prior_result(self, source_channel: str, turn_id: str):
        if not turn_id:
            return None
        key = _event_key(source_channel, turn_id)
        for item in reversed(self._load_results().get('items', [])):
            if isinstance(item, dict) and item.get('event_key') == key and isinstance(item.get('result'), dict):
                return dict(item['result'])
        return None

    def _store_result(self, source_channel: str, turn_id: str, result: dict) -> None:
        if not turn_id:
            return
        data = self._load_results()
        key = _event_key(source_channel, turn_id)
        if any(isinstance(item, dict) and item.get('event_key') == key for item in data.get('items', [])):
            return
        data.setdefault('items', []).append({
            'event_key': key,
            'source_channel': source_channel,
            'turn_id': turn_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'result': result,
        })
        data['items'] = data['items'][-200:]
        atomic_write_json(self.results_path, data)

    def _knowledge_base_matches(self, query: str) -> list[dict]:
        if self.reports_root is None:
            return []
        root = self.reports_root / 'KnowledgeBase'
        if not root.is_dir():
            return []
        terms = [
            value.lower() for value in re.findall(r'[A-Za-zÀ-ÿ0-9_.-]{4,}', query or '')
            if value.lower() not in {'staat', 'er', 'in', 'over', 'wat', 'knowledge', 'base', 'kennisbank'}
        ]
        results = []
        for path in sorted(root.glob('*.md')):
            try:
                text = path.read_text(encoding='utf-8')
            except OSError:
                continue
            safe_lines = [line for line in text.splitlines() if not contains_secret_text(line)]
            safe = '\n'.join(safe_lines)
            lowered = safe.lower()
            if terms and not any(term in lowered for term in terms):
                continue
            position = min([lowered.find(term) for term in terms if term in lowered] or [0])
            start = max(0, position - 160)
            snippet = safe[start:start + 700].strip()
            if snippet:
                results.append({'path': str(path), 'snippet': snippet})
            if len(results) >= 5:
                break
        return results

    def _truth(self, status: dict, *, query: str = '') -> dict:
        manager = status.get('manager', {}) if isinstance(status.get('manager'), dict) else {}
        progress = status.get('progress', {}) if isinstance(status.get('progress'), dict) else {}
        roadmap = load_json(self.root / 'roadmap' / 'queue.json', default={})
        tasks_payload = load_json(self.root / 'state' / 'tasks.json', default={})
        tasks = tasks_payload.get('tasks', []) if isinstance(tasks_payload, dict) and isinstance(tasks_payload.get('tasks'), list) else []
        truth = {
            'release_version': str((status.get('release') or {}).get('version') or ''),
            'pm_version': str(manager.get('version') or status.get('projectmanager_version') or ''),
            'mode': str(status.get('mode') or ''),
            'progress': progress,
            'next_action': status.get('next_action') or progress.get('next_action'),
            'active_task': status.get('active_task'),
            'blockers': list(progress.get('blockers') or []),
            'open_issues': status.get('open_issues', []),
            'open_approvals': status.get('decisions_needed', []),
            'release_chain': status.get('release_chain', {}),
            'roadmap': roadmap if isinstance(roadmap, dict) and roadmap else status.get('canonical_roadmap', {}),
            'tasks': tasks,
        }
        if _KB_QUERY.search(query or ''):
            truth['knowledge_base'] = self._knowledge_base_matches(query)
        return truth

    @staticmethod
    def _speech_for_truth(truth: dict) -> str:
        release = truth.get('release_version') or 'onbekend'
        label = (truth.get('progress') or {}).get('step_label') or 'voortgang onbekend'
        blockers = truth.get('blockers') or []
        next_action = truth.get('next_action') or 'nog niet bepaald'
        if blockers:
            return f'{release}: {label}. Blocker: {blockers[0]}. Volgende stap: {next_action}.'
        return f'{release}: {label}. Geen blocker. Volgende stap: {next_action}.'

    @staticmethod
    def _parameters(action: str, text: str, status: dict) -> dict:
        versions = _VERSION.findall(text or '')
        version = versions[0] if versions else ''
        if action == 'production_deploy':
            lowered = (text or '').lower()
            if 'home assistant' in lowered or re.search(r'\bha\b', lowered):
                target = 'Home Assistant'
            elif 'green' in lowered:
                target = 'Home Assistant Green'
            elif 'productie' in lowered or 'production' in lowered:
                target = 'production'
            else:
                target = 'production'
            if not version:
                version = str((status.get('release') or {}).get('version') or '')
            return {'version': version, 'target': target}
        if action == 'architecture_change':
            lowered = (text or '').lower()
            target = 'Claude Cowork' if 'claude cowork' in lowered else 'systeemarchitectuur'
            return {'version': version, 'target': target}
        if action == 'native_mcp_reload':
            return {'version': version, 'target': 'energie-filesystem-mcp'}
        return {}

    def _challenge(self, action: str, text: str, source_channel: str, session_id: str, status: dict, *, now=None):
        parameters = self._parameters(action, text, status)
        result = self.approval.request(action=action, parameters=parameters, source_channel=source_channel, now=now)
        challenge = result.get('challenge', {}) if isinstance(result, dict) else {}
        challenge_id = str(challenge.get('id') or '')
        self._update_session(
            session_id,
            active_challenge_id=challenge_id,
            active_challenge_parameters=parameters,
            active_protected_action=action,
        )
        return {
            'status': 'confirmation_required',
            'challenge_id': challenge_id,
            'prompt': result.get('prompt'),
            'action': action,
            'parameters': parameters,
            'speech': result.get('prompt'),
        }

    def _handle_confirmation(self, text: str, source_channel: str, session_id: str, confidence, *, now=None):
        session = self._session(session_id)
        challenge_id = str(session.get('active_challenge_id') or '')
        if not challenge_id or not _explicit_confirmation(text):
            return None
        if source_channel in _SPEECH_CHANNELS and confidence is not None and confidence < 0.70:
            return {
                'status': 'confirmation_required',
                'reason': 'uncertain_voice_confirmation',
                'challenge_id': challenge_id,
                'speech': 'Ik heb de bevestiging niet zeker genoeg verstaan. Bevestig de actie opnieuw expliciet.',
            }
        result = self.approval.confirm(
            challenge_id,
            text,
            source_channel=source_channel,
            parameters=session.get('active_challenge_parameters'),
            now=now,
        )
        if result.get('status') == 'approved':
            self._update_session(session_id, active_challenge_id='', active_challenge_parameters={}, active_protected_action='')
        response = dict(result)
        response['speech'] = (
            'De beschermde actie is definitief goedgekeurd en gaat via de normale Projectmanager-uitvoergate.'
            if result.get('status') == 'approved'
            else 'De beschermde actie is nog niet goedgekeurd.'
        )
        return response

    def handle(
        self, *, text: str, source_channel: str, turn_id: str = '', session_id: str = '',
        transcript_id: str = '', transcript_confidence=None, now=None,
    ) -> dict:
        text = str(text or '').strip()
        source_channel = str(source_channel or '').strip().lower() or 'chatgpt'
        turn_id = str(turn_id or '').strip() or uuid4().hex
        session_id = str(session_id or '').strip() or 'default'
        confidence = _safe_confidence(transcript_confidence)
        if not text:
            return {'status': 'blocked', 'reason': 'empty_transcript', 'speech': 'Ik heb geen bruikbare opdracht ontvangen.'}

        prior = self._prior_result(source_channel, turn_id)
        if prior is not None:
            return prior

        confirmation = self._handle_confirmation(text, source_channel, session_id, confidence, now=now)
        if confirmation is not None:
            self._store_result(source_channel, turn_id, confirmation)
            return confirmation

        status = self._load_status()

        if is_new_chat_intent(text):
            snapshot = self.handover.create(
                source_channel=source_channel,
                trigger_text=text,
                trigger_id=turn_id,
                now=now,
            )
            result = {
                'status': 'handover_ready',
                'handover_id': snapshot.get('handover_id'),
                'snapshot': snapshot,
                'speech': f"Overdracht staat klaar. De volgende chat hervat vanaf {snapshot.get('progress', {}).get('step_label', 'de actuele stap')}.",
            }
            self._store_result(source_channel, turn_id, result)
            return result

        blocker = None
        resolved_text = text
        progress = status.get('progress', {}) if isinstance(status.get('progress'), dict) else {}
        blockers = progress.get('blockers') if isinstance(progress.get('blockers'), list) else []
        if _DEICTIC_BLOCKER.search(text) and blockers:
            blocker = str(blockers[0])
            resolved_text = f'{text} {blocker}'

        action = protected_action_kind(resolved_text)
        if action:
            result = self._challenge(action, resolved_text, source_channel, session_id, status, now=now)
            if blocker:
                result['resolved_context'] = {'blocker': blocker}
            self._store_result(source_channel, turn_id, result)
            return result

        if _matches(text, _STATUS_PATTERNS) or _ROADMAP_OR_TASK_QUERY.search(text) or _KB_QUERY.search(text):
            truth = self._truth(status, query=text)
            result = {'status': 'answered', 'truth': truth, 'speech': self._speech_for_truth(truth)}
            self._update_session(session_id, last_truth=truth, last_blocker=(truth.get('blockers') or [''])[0])
            self._store_result(source_channel, turn_id, result)
            return result

        command = {
            'text': text,
            'source_channel': source_channel,
            'source_ref': turn_id,
            'ingress_id': turn_id,
            'transcript_id': str(transcript_id or '').strip(),
            'transcript_confidence': confidence,
        }
        intake_result = self.intake.accept(command)
        result = {
            'status': intake_result.get('status', 'accepted'),
            'intake': intake_result,
            'speech': 'Opdracht is via de centrale Projectmanager-intake verwerkt.',
        }
        if blocker:
            result['resolved_context'] = {'blocker': blocker}
            self._update_session(session_id, last_blocker=blocker)
        self._store_result(source_channel, turn_id, result)
        return result
