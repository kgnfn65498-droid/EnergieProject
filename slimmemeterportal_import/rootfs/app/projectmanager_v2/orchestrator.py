from pathlib import Path

from approval_ingress import ApprovalIngressConsumer
from approved_action_store import ApprovedActionStore
from command_ingress import CommandIngressConsumer
from command_processor import CommandProcessor
from command_store import CommandStore
from configured_service import ConfiguredManagerService
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer
from handover import build_handover
from mode_bridge import ModeBridge
from nas_container_cr_service import ConfiguredNasContainerCrService
from persistence import atomic_write_json
from protected_action_executor import ProtectedActionExecutor
from roadmap_regie import RoadmapRegie


def _read_manager_version(app_root) -> str:
    path = Path(app_root or '.') / 'VERSION.txt'
    try:
        return path.read_text(encoding='utf-8').strip() or 'NOG_TE_CONTROLEREN'
    except OSError:
        return 'NOG_TE_CONTROLEREN'


class ProjectmanagerRuntime:
    def __init__(self, config, *, base_service=None, nas_container_cr_service=None):
        self.config = config
        self.base = base_service or ConfiguredManagerService(config)
        root = Path(config.system_root)
        self.root = root
        self.commands = CommandStore(root / 'commands' / 'queue.json')
        self.approved_actions = ApprovedActionStore(root / 'approved_actions' / 'queue.json')
        self.handoffs = getattr(self.base, 'handoffs', None) or HandoffQueue(root / 'handoffs' / 'queue.json')
        self.roadmap = getattr(self.base, 'roadmap', None) or RoadmapRegie(root / 'roadmap' / 'queue.json')

        recovered = self.commands.recover_interrupted()
        self.recovered_commands = recovered
        if recovered:
            issues = getattr(self.base, 'issues', None)
            if issues is not None:
                issues.open(
                    'commands:interrupted_after_restart',
                    severity='ORANGE',
                    title='Projectmanager commands onderbroken door restart',
                    details={'count': len(recovered), 'command_ids': [item.get('id') for item in recovered[:20]]},
                )
            self.base.audit.write(
                'command.restart_recovery',
                actor='projectmanager',
                result='safe',
                details={'count': len(recovered)},
            )

        mode_bridge = ModeBridge(config.mode_command_path) if getattr(config, 'mode_command_path', '') else None
        if nas_container_cr_service is None:
            nas_container_cr_service = ConfiguredNasContainerCrService(
                config.project_root,
                private_root=getattr(config, 'nas_docker_tls_root', '/data/projectmanager_v2/docker_tls'),
            )
        self.nas_container_cr_service = nas_container_cr_service
        self.processor = CommandProcessor(
            self.commands,
            self.base.decisions,
            self.base.mode,
            self.base.tasks,
            audit=self.base.audit,
            mode_bridge=mode_bridge,
            approved_actions=self.approved_actions,
            nas_container_cr_service=self.nas_container_cr_service,
        )
        ingress_root = getattr(config, 'command_ingress_root', '') or ''
        self.ingress = CommandIngressConsumer(
            ingress_root or None,
            root / 'commands' / 'ingress_receipts.json',
            self.commands,
        )
        approval_root = getattr(config, 'approval_ingress_root', '') or ''
        self.approvals = ApprovalIngressConsumer(
            approval_root or None,
            root / 'decisions' / 'approval_ingress_receipts.json',
            self.base.decisions,
        )
        handoff_result_root = getattr(config, 'handoff_result_ingress_root', '') or ''
        self.handoff_results = HandoffResultIngressConsumer(
            handoff_result_root or None,
            root / 'handoffs' / 'result_ingress_receipts.json',
            self.handoffs,
            self.base.tasks,
            self.roadmap,
        )
        self.protected_executor = ProtectedActionExecutor(
            config.project_root,
            self.approved_actions,
            self.commands,
            self.base.decisions,
            audit=self.base.audit,
        )

    def _open_issue(self, fingerprint, *, severity, title, details):
        issues = getattr(self.base, 'issues', None)
        if issues is not None:
            issues.open(fingerprint, severity=severity, title=title, details=details)

    def run_once(self, *, now=None):
        handoff_results = self.handoff_results.consume(max_items=20)
        for result in handoff_results:
            self.base.audit.write(
                'handoff.result_ingress',
                actor='projectmanager',
                result='ok' if result.get('status') == 'APPLIED' else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"handoff_result_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Extern handoff-resultaat geweigerd',
                    details={'reason': result.get('reason')},
                )

        approval_results = self.approvals.consume(max_items=20)
        for result in approval_results:
            self.base.audit.write(
                'approval.ingress',
                actor='projectmanager',
                result='ok' if result.get('status') in {'APPLIED', 'IGNORED_ALREADY_RESOLVED'} else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"approval_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Lokale Projectmanager-goedkeuring geweigerd',
                    details={'reason': result.get('reason')},
                )

        ingress_results = self.ingress.consume(max_items=20)
        for result in ingress_results:
            self.base.audit.write(
                'command.ingress',
                actor='projectmanager',
                result='ok' if result.get('status') == 'IMPORTED' else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"command_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Extern Projectmanager-command geweigerd',
                    details={'reason': result.get('reason')},
                )

        processed = self.processor.process_all(max_items=50)
        protected_results = self.protected_executor.run_once(max_items=5)
        status = dict(self.base.run_once(now=now))
        status['manager'] = {'version': _read_manager_version(getattr(self.config, 'manager_app_root', ''))}
        status['handoff_result_ingress_results'] = handoff_results[-20:]
        status['approval_ingress_results'] = approval_results[-20:]
        status['ingress_results'] = ingress_results[-20:]
        status['processed_commands'] = len(processed)
        status['protected_executor_results'] = protected_results[-20:]
        if processed:
            status['command_results'] = processed[-20:]
        status['interrupted_commands'] = len(self.commands.by_status('INTERRUPTED'))
        status['approved_actions'] = self.approved_actions.open_items()
        status['handoffs'] = self.handoffs.open_items()
        status['canonical_roadmap'] = self.roadmap.canonical_metadata()
        self._refresh_coordination(status)
        return status

    def _refresh_coordination(self, status: dict):
        current_mode = self.base.mode.get()
        active = self.base.tasks.active()
        decisions = self.base.decisions.pending()
        status['mode'] = current_mode.get('mode', status.get('mode', 'USER'))
        status['active_task'] = active
        status['decisions_needed'] = decisions
        status['needs_human'] = bool(decisions)
        status['next_action'] = (active or {}).get('next_action')
        status['pending_commands'] = self.commands.pending_count()
        status['approved_actions'] = self.approved_actions.open_items()
        status['handoffs'] = self.handoffs.open_items()
        status['canonical_roadmap'] = self.roadmap.canonical_metadata()
        issues = getattr(self.base, 'issues', None)
        status['open_issues'] = issues.open_items() if issues is not None else status.get('open_issues', [])
        atomic_write_json(self.root / 'status' / 'current.json', status)
        handover = build_handover(
            mode=current_mode,
            active_task=active,
            release=status.get('release') or {},
            decisions=decisions,
            evidence=(status.get('health') or {}).get('checks', []),
            last_changes=[
                f"command:{item.get('intent')}:{item.get('status')}"
                for item in status.get('command_results', [])
            ],
        )
        handover['manager'] = status.get('manager', {})
        handover['open_issues'] = status.get('open_issues', [])
        handover['interrupted_commands'] = status.get('interrupted_commands', 0)
        handover['approved_actions'] = status.get('approved_actions', [])
        handover['handoffs'] = status.get('handoffs', [])
        handover['canonical_roadmap'] = status.get('canonical_roadmap', {})
        atomic_write_json(self.root / 'handover' / 'current.json', handover)
