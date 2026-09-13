import json
from pathlib import Path


POLICY_SCHEMA_V1 = 'energie_native_mcp_self_heal_policy_v1'
POLICY_SCOPE_V1 = 'release_bound_native_mcp_self_reload_after_accepted_release'
POLICY_SCHEMA_V2 = 'energie_native_mcp_self_heal_policy_v2'
POLICY_SCOPE_V2 = 'release_bound_native_mcp_self_reload_during_live_acceptance_or_accepted'


class NativeMcpSelfHealAuthorizer:
    """Apply Peter's standing approval only to the exact release-bound Native MCP self-heal.

    This does not authorize arbitrary restarts. It only resolves the one canonical
    projectmanager_auto native_mcp_reload decision for the current release,
    after exact release-bound safety conditions are proven and the runtime guard proves reload is needed.
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
        schema = policy.get('schema')
        scope = policy.get('scope')
        contract_ok = (
            (schema == POLICY_SCHEMA_V1 and scope == POLICY_SCOPE_V1)
            or (schema == POLICY_SCHEMA_V2 and scope == POLICY_SCOPE_V2)
        )
        return (
            contract_ok
            and policy.get('enabled') is True
            and policy.get('approved_by') == 'Peter'
            and 'native_mcp_reload' in (policy.get('authorized_for') or ['native_mcp_reload'])
        )

    @staticmethod
    def _live_acceptance_hold_safe(hold):
        if not isinstance(hold, dict):
            return False
        checks = hold.get('validation_checks')
        if not isinstance(checks, dict):
            return False
        required_green = (
            'version', 'web_runtime', 'state_io', 'automatic_runtime_idle',
            'release_chain', 'production_certificate',
        )
        if any(not isinstance(checks.get(name), dict) or checks[name].get('ok') is not True for name in required_green):
            return False
        audit_check = checks.get('projectmanager_self_audit')
        if not isinstance(audit_check, dict) or audit_check.get('ok') is not False:
            return False
        reasons = {str(item).strip() for item in (hold.get('reasons') or []) if str(item).strip()}
        return reasons == {'projectmanager_self_audit'}

    def _eligible_release(self):
        try:
            release = self.version_path.read_text(encoding='utf-8').strip()
        except OSError:
            return None, 'live_release_unreadable', None
        if not release:
            return None, 'live_release_unreadable', None

        atomic = self._json(self.atomic_path)
        atomic_state = str((atomic or {}).get('state') or '').strip().upper()
        if not atomic or str(atomic.get('to_version') or '').strip() != release:
            return None, 'release_not_current_atomic_target', None

        hold = self._json(self.hold_path)
        hold_release = str((hold or {}).get('release_version') or '').strip()
        if atomic_state == 'ACCEPTED':
            if (
                not hold
                or hold.get('active') is not False
                or hold.get('validation_status') != 'ok'
                or hold_release != release
            ):
                return None, 'release_validation_not_green', None
            release_phase = 'ACCEPTED'
        elif atomic_state == 'LIVE_ACCEPTANCE':
            policy = self._json(self.policy_path) or {}
            if not (policy.get('schema') == POLICY_SCHEMA_V2 and policy.get('scope') == POLICY_SCOPE_V2):
                return None, 'release_not_accepted', None
            if (
                not hold
                or hold.get('active') is not True
                or hold.get('validation_status') not in {'required', 'blocked'}
                or hold_release != release
                or not self._live_acceptance_hold_safe(hold)
            ):
                return None, 'live_acceptance_not_safe_for_native_mcp_self_heal', None
            release_phase = 'LIVE_ACCEPTANCE'
        else:
            return None, 'release_not_accepted', None

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
            return None, 'native_mcp_reload_not_required', None
        return release, None, release_phase

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

        release, reason, release_phase = self._eligible_release()
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
            'release_phase': release_phase,
            'decision_id': approved['id'],
            'command_id': ready['id'],
            'policy_path': str(self.policy_path),
        }
        if self.audit is not None:
            self.audit.write('native_mcp.self_heal_authorization', actor='projectmanager', result='approved', details=result)
        return result
