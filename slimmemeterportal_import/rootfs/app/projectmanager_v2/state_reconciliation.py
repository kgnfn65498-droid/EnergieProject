from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re


FINAL_TASK_STATUSES = {'DONE', 'SUPERSEDED'}
PURE_MODE_INTENTS = {'start_development', 'start_maintenance'}
LEGACY_DEVELOPMENT_TASK_ID = '9baa6fc1ae384379a1192004762bf8fa'


def _clean_refs(values):
    return list(dict.fromkeys(str(item).strip() for item in (values or []) if str(item).strip()))


def _release_validation_green(release_validation):
    if not isinstance(release_validation, dict):
        return False
    status = str(release_validation.get('validation_status') or release_validation.get('status') or '').strip().lower()
    return release_validation.get('active') is False and status == 'ok'


def _runtime_mode(runtime):
    return str(((runtime or {}).get('operating_mode') or {}).get('effective_mode') or '').strip()


def _mode_evidence(runtime, release_validation):
    refs = []
    mode_source = ((runtime or {}).get('operating_mode') or {}).get('source')
    if mode_source:
        refs.append(str(mode_source))
    if isinstance(release_validation, dict):
        source = release_validation.get('_source') or release_validation.get('source')
        if source:
            refs.append(str(source))
    return _clean_refs(refs)




def _native_mcp_green(runtime):
    guard = (runtime or {}).get('native_mcp_runtime')
    if not isinstance(guard, dict):
        return False, []
    expected = str(guard.get('expected_fingerprint') or '').lower()
    actual = str(guard.get('runtime_fingerprint') or '').lower()
    ok = (
        guard.get('status') == 'GREEN'
        and guard.get('ready') is True
        and guard.get('reload_required') is False
        and len(expected) == 64
        and expected == actual
    )
    return ok, _clean_refs([guard.get('source')])

def _pure_mode_command(decision, command):
    if not isinstance(command, dict):
        return False
    context = decision.get('context') or {}
    if command.get('status') != 'WAITING_APPROVAL':
        return False
    if command.get('approval_decision_id') != decision.get('id'):
        return False
    intent = command.get('intent') or context.get('intent')
    if intent not in PURE_MODE_INTENTS:
        return False
    protected_payload_fields = (
        'artifact_path', 'artifact_sha256', 'release_version', 'verification_report',
    )
    for field in protected_payload_fields:
        if str(command.get(field) or context.get(field) or '').strip():
            return False
    return True


def _release_tuple(value):
    try:
        parts = tuple(int(part) for part in str(value or '').strip().split('.'))
    except ValueError:
        return None
    return parts if len(parts) == 3 else None


def _task_release(task):
    metadata = task.get('build_metadata') if isinstance(task.get('build_metadata'), dict) else {}
    for value in (metadata.get('release_version'), task.get('release_version')):
        parsed = _release_tuple(value)
        if parsed:
            return str(value), parsed
    for field in ('title', 'goal', 'next_action'):
        match = re.search(r'(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+)(?![0-9])', str(task.get(field) or ''))
        if match:
            parsed = _release_tuple(match.group(1))
            if parsed:
                return match.group(1), parsed
    return None, None


def _is_release_build_task(task):
    metadata = task.get('build_metadata') if isinstance(task.get('build_metadata'), dict) else {}
    if task.get('build_contract_required') is True or _release_tuple(metadata.get('release_version')):
        return True
    text = ' '.join(str(task.get(field) or '') for field in ('title', 'goal')).lower()
    if 'build' in text:
        return True
    # Narrow legacy migration: pre-contract release-ingress continuation tasks
    # are release work, but ordinary tasks containing only a version number are not.
    return bool(re.search(r'\brelease[- ]ingress\b', text))


class StateReconciler:
    def __init__(self, tasks, decisions, commands, handoffs, issues, audit=None):
        self.tasks = tasks
        self.decisions = decisions
        self.commands = commands
        self.handoffs = handoffs
        self.issues = issues
        self.audit = audit

    def _evaluate_decision(self, decision, command, runtime, release_validation):
        if decision.get('status') == 'SUPERSEDED':
            return {
                'disposition': 'SUPERSEDED',
                'reason': decision.get('superseded_reason') or 'already superseded',
                'evidence_refs': _clean_refs(decision.get('superseded_evidence_refs')),
                'changed': False,
            }
        if decision.get('status') in {'APPROVED', 'REJECTED'}:
            return None
        if decision.get('status') != 'PENDING':
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': f"unsupported decision state: {decision.get('status')}",
                'evidence_refs': [],
                'changed': False,
            }
        if decision.get('kind') != 'MODE_CHANGE':
            context = decision.get('context') or {}
            intent = str((command or {}).get('intent') or context.get('intent') or '').strip()
            if decision.get('kind') == 'PRODUCTION_RESTART' and intent == 'native_mcp_reload':
                green, refs = _native_mcp_green(runtime)
                if green and refs and isinstance(command, dict) and command.get('status') == 'WAITING_APPROVAL' and command.get('approval_decision_id') == decision.get('id'):
                    return {
                        'disposition': 'SUPERSEDED',
                        'reason': 'native MCP exact runtime fingerprint is already GREEN; restart no longer required',
                        'evidence_refs': refs,
                        'changed': True,
                    }
            return {
                'disposition': 'ACTIVE_KEEP',
                'reason': 'protected decision remains for Peter; no automatic reconciliation rule',
                'evidence_refs': [],
                'changed': False,
            }

        context = decision.get('context') or {}
        target = str(context.get('target_mode') or '').strip()
        current = _runtime_mode(runtime)
        refs = _mode_evidence(runtime, release_validation)
        if not target or not current:
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': 'mode target or authoritative runtime mode missing',
                'evidence_refs': refs,
                'changed': False,
            }
        if target != current:
            return {
                'disposition': 'ACTIVE_KEEP',
                'reason': f'target mode {target} differs from authoritative runtime mode {current}',
                'evidence_refs': refs,
                'changed': False,
            }
        if not _release_validation_green(release_validation):
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': 'target mode already active but release validation is not explicitly released_ok',
                'evidence_refs': refs,
                'changed': False,
            }
        if not _pure_mode_command(decision, command):
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': 'mode decision is not linked to an unambiguous pure WAITING_APPROVAL mode command',
                'evidence_refs': refs,
                'changed': False,
            }
        if len(refs) < 2:
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': 'authoritative mode/release evidence references are incomplete',
                'evidence_refs': refs,
                'changed': False,
            }
        return {
            'disposition': 'SUPERSEDED',
            'reason': f'target mode {target} is already authoritative and release validation is released_ok',
            'evidence_refs': refs,
            'changed': True,
        }

    def _evaluate_task(self, task, runtime=None, release_validation=None):
        if task.get('status') in FINAL_TASK_STATUSES:
            return None
        if task.get('id') == LEGACY_DEVELOPMENT_TASK_ID:
            mode = _runtime_mode(runtime)
            release = (runtime or {}).get('release') or {}
            release_version = str(release.get('version') or '').strip()
            refs = _clean_refs([
                release.get('source'),
                ((runtime or {}).get('operating_mode') or {}).get('source'),
                (release_validation or {}).get('_source') or (release_validation or {}).get('source'),
            ])
            if mode == 'DEVELOPMENT' and release_version and _release_validation_green(release_validation) and len(refs) == 3:
                return {
                    'disposition': 'SUPERSEDED',
                    'reason': 'exact known legacy development-mode task is satisfied by authoritative DEVELOPMENT runtime and released validation',
                    'evidence_refs': refs,
                    'changed': True,
                    'superseded_by': 'state_reconciliation:legacy_task_rule',
                }
            return {
                'disposition': 'REVIEW_REQUIRED',
                'reason': 'exact legacy task found but authoritative mode/release evidence is incomplete',
                'evidence_refs': refs,
                'changed': False,
            }
        task_release, task_tuple = _task_release(task)
        release = (runtime or {}).get('release') or {}
        live_release = str(release.get('version') or release.get('ha_runtime_version') or '').strip()
        live_tuple = _release_tuple(live_release)
        release_chain = (runtime or {}).get('release_chain') or {}
        atomic = release_chain.get('atomic_swap') or {}
        atomic_raw = atomic.get('raw') if isinstance(atomic.get('raw'), dict) else {}
        atomic_state = str(atomic.get('state') or atomic_raw.get('state') or '')
        atomic_to = str(atomic_raw.get('to_version') or '')
        refs = _clean_refs([release.get('source'), atomic.get('source')])
        if task_tuple and live_tuple and task.get('mode') == 'DEVELOPMENT' and _is_release_build_task(task) and refs:
            installed_newer = live_tuple > task_tuple
            same_release_installed = live_tuple == task_tuple and atomic_to == task_release and atomic_state in {'LIVE_ACCEPTANCE', 'ACCEPTED'}
            if installed_newer or same_release_installed:
                return {'disposition': 'SUPERSEDED','reason': f'release build phase superseded by authoritative runtime {live_release} atomic={atomic_state}','evidence_refs': refs,'changed': True,'superseded_by': 'state_reconciliation:runtime_release_rule'}
        proof = task.get('reconciliation_proof')
        if isinstance(proof, dict) and proof.get('goal_satisfied') is True:
            refs = _clean_refs(proof.get('evidence_refs'))
            reason = str(proof.get('reason') or '').strip()
            if refs and reason:
                return {
                    'disposition': 'SUPERSEDED',
                    'reason': reason,
                    'evidence_refs': refs,
                    'changed': True,
                    'superseded_by': proof.get('superseded_by'),
                }
        return {
            'disposition': 'REVIEW_REQUIRED',
            'reason': 'no explicit machine-verifiable task completion/supersede proof',
            'evidence_refs': [],
            'changed': False,
        }

    def reconcile(self, *, runtime, release_validation=None, now=None, issue_repairs=None):
        now = now or datetime.now(timezone.utc)
        results = []

        for decision in self.decisions.all():
            command = None
            command_id = (decision.get('context') or {}).get('command_id')
            if command_id:
                try:
                    command = self.commands.get(command_id)
                except KeyError:
                    command = None
            evaluated = self._evaluate_decision(decision, command, runtime, release_validation)
            if evaluated is None:
                continue
            changed = False
            if evaluated['disposition'] == 'SUPERSEDED' and decision.get('status') == 'PENDING':
                final = self.decisions.supersede(
                    decision['id'],
                    reason=evaluated['reason'],
                    evidence_refs=evaluated['evidence_refs'],
                    superseded_by='state_reconciliation',
                    now=now,
                )
                if command is not None and command.get('status') == 'WAITING_APPROVAL':
                    self.commands.cancel(
                        command['id'],
                        reason='superseded_by_state_reconciliation:' + evaluated['reason'],
                    )
                changed = final.get('status') == 'SUPERSEDED'
            results.append({
                'entity_type': 'decision',
                'id': decision.get('id'),
                **evaluated,
                'changed': changed if evaluated['disposition'] == 'SUPERSEDED' else False,
            })

        for task in self.tasks.all():
            evaluated = self._evaluate_task(task, runtime=runtime, release_validation=release_validation)
            if evaluated is None:
                continue
            changed = False
            if evaluated['disposition'] == 'SUPERSEDED' and task.get('status') != 'SUPERSEDED':
                final = self.tasks.supersede(
                    task['id'],
                    reason=evaluated['reason'],
                    evidence_refs=evaluated['evidence_refs'],
                    superseded_by=evaluated.get('superseded_by') or 'state_reconciliation',
                    now=now,
                )
                changed = final.get('status') == 'SUPERSEDED'
            results.append({
                'entity_type': 'task',
                'id': task.get('id'),
                'disposition': evaluated['disposition'],
                'reason': evaluated['reason'],
                'evidence_refs': evaluated['evidence_refs'],
                'changed': changed,
            })

        if self.handoffs is not None:
            for handoff in self.handoffs.open_items():
                results.append({
                    'entity_type': 'handoff',
                    'id': handoff.get('id'),
                    'disposition': 'ACTIVE_KEEP',
                    'reason': 'open handoff is never auto-closed by generic reconciliation',
                    'evidence_refs': [],
                    'changed': False,
                })
        if self.issues is not None:
            repair_map = issue_repairs if isinstance(issue_repairs, dict) else {}
            for issue in self.issues.open_items():
                repair = repair_map.get(issue.get('id'))
                if isinstance(repair, dict):
                    refs = _clean_refs(repair.get('evidence_refs'))
                    reason = str(repair.get('reason') or '').strip()
                    if refs and reason:
                        self.issues.resolve(issue['id'], resolution=reason + ' | evidence=' + ';'.join(refs))
                        results.append({
                            'entity_type': 'issue',
                            'id': issue.get('id'),
                            'disposition': 'RESOLVED',
                            'reason': reason,
                            'evidence_refs': refs,
                            'changed': True,
                        })
                        continue
                results.append({
                    'entity_type': 'issue',
                    'id': issue.get('id'),
                    'disposition': 'ACTIVE_KEEP',
                    'reason': 'open issue requires an exact coded repair-evidence rule before resolution',
                    'evidence_refs': [],
                    'changed': False,
                })

        counts = Counter(item['disposition'] for item in results)
        summary = {
            'schema': 1,
            'evaluated_at': now.isoformat(),
            'counts': {
                'ACTIVE_KEEP': counts.get('ACTIVE_KEEP', 0),
                'SUPERSEDED': counts.get('SUPERSEDED', 0),
                'REVIEW_REQUIRED': counts.get('REVIEW_REQUIRED', 0),
                'RESOLVED': counts.get('RESOLVED', 0),
            },
            'changed_count': sum(1 for item in results if item.get('changed')),
            'items': results,
        }
        if self.audit is not None:
            self.audit.write(
                'state.reconciliation',
                actor='projectmanager',
                result='ok',
                details={'counts': summary['counts'], 'changed_count': summary['changed_count']},
            )
        return summary
