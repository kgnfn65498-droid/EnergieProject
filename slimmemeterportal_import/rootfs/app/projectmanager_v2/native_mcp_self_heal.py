import json
from pathlib import Path


POLICY_SCHEMA = 'energie_native_mcp_self_heal_policy_v1'
POLICY_SCOPE = 'release_bound_native_mcp_self_reload_after_accepted_release'


class NativeMcpSelfHealAuthorizer:
    """Apply Peter's standing approval only to the exact release-bound Native MCP self-heal.

    This does not authorize arbitrary restarts. It only resolves the one canonical
    projectmanager_auto native_mcp_reload decision for the currently accepted release,
    after release validation is already green and the runtime guard proves reload is needed.
    """

    def __init__(self, project_root, commands, decisions, *, audit=None):
        self.project_root = Path(project_root)
        self.commands = commands
        self.decisions = decisions
        self.audit = audit
        self.policy_path = self.project_root / 'Data/03_Systeem/Projectmanager/Policies/native_mcp_self_heal_policy.json'
        self.atomic_path = self.project_root / 'Inbox/atomic_app_swap_state.json'
        self.hold_path = self.project_root / 'Inbox/operating_mode/release_validation_hold.json'
        self.guard_path = self.project_root / 'Inbox/native_mcp_runtime/runtime_guard.json'
        self.version_path = self.project_root / 'App/VERSIE.txt'

    @staticmethod
    def _json(path: Path):
        if not path.is_file() or path.is_symlink():
            return None
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _blocked(self, reason, **extra):
        result = {'status': 'BLOCKED', 'reason': reason, **extra}
        if self.audit is not None:
            self.audit.write('native_mcp.self_heal_authorization', actor='projectmanager', result='blocked', details=result)
        return result

    def _policy_enabled(self):
        policy = self._json(self.policy_path)
        if not policy:
            return False
        return (
            policy.get('schema') == POLICY_SCHEMA
            and policy.get('enabled') is True
            and policy.get('approved_by') == 'Peter'
            and policy.get('scope') == POLICY_SCOPE
            and 'native_mcp_reload' in (policy.get('authorized_for') or ['native_mcp_reload'])
        )

    def _accepted_release(self):
        try:
            release = self.version_path.read_text(encoding='utf-8').strip()
        except OSError:
            return None, 'live_release_unreadable'
        if not release:
            return None, 'live_release_unreadable'

        atomic = self._json(self.atomic_path)
        if not atomic or atomic.get('state') != 'ACCEPTED' or str(atomic.get('to_version') or '').strip() != release:
            return None, 'release_not_accepted'

        hold = self._json(self.hold_path)
        if (
            not hold
            or hold.get('active') is not False
            or hold.get('validation_status') != 'ok'
            or str(hold.get('release_version') or '').strip() != release
        ):
            return None, 'release_validation_not_green'

        guard = self._json(self.guard_path)
        expected = str((guard or {}).get('expected_fingerprint') or '').lower()
        runtime = str((guard or {}).get('runtime_fingerprint') or '').lower()
        if (
            not guard
            or guard.get('status') != 'RELOAD_REQUIRED'
            or guard.get('reload_required') is not True
            or guard.get('ready') is True
            or len(expected) != 64
            or any(ch not in '0123456789abcdef' for ch in expected)
            or expected == runtime
        ):
            return None, 'native_mcp_reload_not_required'
        return release, None

    def _candidate(self, release):
        matches = []
        for decision in self.decisions.pending():
            if decision.get('kind') != 'PRODUCTION_RESTART':
                continue
            context = decision.get('context') if isinstance(decision.get('context'), dict) else {}
            if context.get('intent') != 'native_mcp_reload':
                continue
            if str(context.get('release_version') or '').strip() != release:
                continue
            command_id = str(context.get('command_id') or '').strip()
            if not command_id:
                continue
            try:
                command = self.commands.get(command_id)
            except KeyError:
                continue
            if (
                command.get('intent') != 'native_mcp_reload'
                or command.get('source') != 'projectmanager_auto'
                or command.get('status') != 'WAITING_APPROVAL'
                or command.get('approval_decision_id') != decision.get('id')
                or str(command.get('release_version') or '').strip() != release
            ):
                continue
            matches.append((decision, command))
        if len(matches) != 1:
            return None
        return matches[0]

    def run_once(self):
        if not self._policy_enabled():
            return self._blocked('standing_policy_not_enabled')

        release, reason = self._accepted_release()
        if reason:
            return self._blocked(reason)

        candidate = self._candidate(release)
        if candidate is None:
            return self._blocked('no_exact_auto_self_heal_candidate', release_version=release)

        decision, command = candidate
        approved = self.decisions.resolve(decision['id'], approved=True, approved_by='Peter')
        ready = self.commands.mark_approved_ready(command['id'])
        result = {
            'status': 'APPROVED',
            'reason': 'standing_policy_exact_release_bound_self_heal',
            'release_version': release,
            'decision_id': approved['id'],
            'command_id': ready['id'],
            'policy_path': str(self.policy_path),
        }
        if self.audit is not None:
            self.audit.write('native_mcp.self_heal_authorization', actor='projectmanager', result='approved', details=result)
        return result
