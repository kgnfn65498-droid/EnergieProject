from datetime import datetime, timezone
from pathlib import Path

from alert_policy import AlertState
from audit_log import AuditLog
from bootstrap import bootstrap_runtime
from decision_queue import DecisionQueue
from document_sync import ManagedDocumentSync
from energy_health_collector import EnergyHealthCollector
from evidence_store import EvidenceStore
from handover import HandoverStore, build_handover
from health_engine import summarize_health
from home_assistant_notifier import HomeAssistantNotifier
from issue_store import IssueStore
from manager_config import ManagerConfig
from market_service import MarketService, NullMarketService
from notification_transport import NotificationOutbox, route_event
from operating_mode import ModeStore
from opportunity_register import OpportunityRegister
from persistence import atomic_write_json
from research_queue import ResearchQueue
from retention import retention_candidates, apply_retention
from roadmap_regie import RoadmapRegie
from runtime_sources import RuntimeCollector
from runtime_truth import evaluate_runtime_first
from self_audit import SelfAuditor
from task_engine import TaskStore
from watchdog import evaluate as watchdog_evaluate


def evidence_summary_from_checks(checks: list) -> list:
    result = []
    for check in checks:
        verified = (
            check.get('evidence_strength') == 'verified'
            and bool(check.get('evidence_ref'))
        )
        result.append({
            'claim': check.get('name'),
            'status': 'BEWEZEN' if verified else 'NOG_TE_CONTROLEREN',
            'evidence_ref': check.get('evidence_ref') if verified else None,
            'result': check.get('status'),
            'reason': check.get('reason'),
        })
    return result


class ManagerService:
    def __init__(self, config: ManagerConfig, *, runtime_collector=None, health_collector=None, notifier=None, market_service=None):
        self.config = config
        self.root = Path(config.system_root)
        self._ensure_layout()
        bootstrap_runtime(self.root)
        self.mode = ModeStore(self.root / 'state' / 'mode.json')
        self.tasks = TaskStore(self.root / 'state' / 'tasks.json')
        self.decisions = DecisionQueue(self.root / 'decisions' / 'queue.json')
        self.evidence = EvidenceStore(self.root / 'state' / 'evidence.json')
        self.issues = IssueStore(self.root / 'issues' / 'issues.json')
        self.opportunities = OpportunityRegister(self.root / 'opportunities' / 'register.json')
        self.research = ResearchQueue(self.root / 'opportunities' / 'research_queue.json')
        self.roadmap = RoadmapRegie(self.root / 'roadmap' / 'queue.json')
        self.audit = AuditLog(self.root / 'audit' / 'events.jsonl')
        self.handover = HandoverStore(self.root / 'handover' / 'current.json')
        self.outbox = NotificationOutbox(self.root / 'notifications' / 'outbox')
        self.alerts = AlertState(self.root / 'notifications' / 'alert_state.json')
        self.runtime_collector = runtime_collector or RuntimeCollector(
            config.project_root,
            mode_state_path=getattr(config, 'mode_state_path', '') or None,
        )
        self.health_collector = health_collector or EnergyHealthCollector(
            config.project_root,
            config.input_root,
            config.recovery_root,
        )
        self.notifier = notifier or HomeAssistantNotifier(
            config.ha_base_url,
            config.ha_token,
            service=config.ha_notify_service or None,
        )
        if market_service is not None:
            self.market = market_service
        elif config.market_enabled:
            self.market = MarketService(self.root / 'market')
        else:
            self.market = NullMarketService()
        self.document_sync = ManagedDocumentSync()
        self.self_auditor = SelfAuditor(
            self.root,
            production_version_path=Path(config.project_root) / 'App' / 'VERSIE.txt',
            canonical_roadmap_path=getattr(config, 'canonical_roadmap_path', '') or None,
        )

    def _ensure_layout(self):
        for name in (
            'state', 'status', 'heartbeat', 'handover', 'audit', 'audit/archive',
            'notifications/outbox', 'notifications/outbox/delivered', 'opportunities',
            'snapshots', 'snapshots/archive', 'self_audit', 'issues', 'market',
            'decisions', 'locks', 'commands', 'roadmap', 'handoffs', 'approved_actions', 'quarantine', 'logs/archive',
        ):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def run_once(self, *, now=None) -> dict:
        now = now or datetime.now(timezone.utc)
        self.audit.write('manager.run.started', actor='projectmanager', result='started')
        runtime = self.runtime_collector.collect()
        self._reconcile_mode(runtime)
        mode_state = self.mode.get()

        checks = self.health_collector.collect(now=now)
        market_events = self.market.run_due(now=now)
        self._record_evidence(checks)
        self._reconcile_issues(checks, market_events)
        research_events = self._reconcile_research(market_events, now=now)
        health = summarize_health(checks)
        watchdog_events = watchdog_evaluate([
            dict(item, type=item.get('name')) for item in checks if item.get('status') != 'GREEN'
        ])

        pending_decisions = self.decisions.pending()
        roadmap_selection = self._maybe_select_roadmap_task(health, pending_decisions)
        active_task = self.tasks.active()
        release = runtime.get('release') or {}
        retention_result = self._apply_safe_retention(now=now)
        handoff_research = self.research.due(now=now, executor='handoff')

        status = {
            'schema': 'energie_projectmanager_status_v2',
            'updated_at': now.isoformat(),
            'project_id': 'energie',
            'mode': mode_state.get('mode', 'USER'),
            'health': health,
            'release': {'version': release.get('version')},
            'active_task': active_task,
            'decisions_needed': pending_decisions,
            'needs_human': bool(pending_decisions),
            'open_issues': self.issues.open_items(),
            'market_events': market_events,
            'research_events': research_events,
            'research_handoffs_due': [
                {'key': item.get('key'), 'query': item.get('query'), 'priority': item.get('priority')}
                for item in handoff_research[:20]
            ],
            'watchdog_events': watchdog_events,
            'retention': retention_result,
            'roadmap_selection': roadmap_selection,
            'next_action': (active_task or {}).get('next_action'),
        }
        atomic_write_json(self.root / 'status' / 'current.json', status)
        atomic_write_json(self.root / 'snapshots' / 'current_runtime.json', {
            'observed_at': now.isoformat(),
            'runtime': runtime,
            'checks': checks,
            'health': health,
            'market_events': market_events,
            'research_events': research_events,
            'config': self.config.public_dict(),
        })

        evidence_summary = evidence_summary_from_checks(checks)
        handover_payload = build_handover(
            mode=mode_state,
            active_task=active_task,
            release=status['release'],
            decisions=pending_decisions,
            evidence=evidence_summary,
            last_changes=[event.get('subject') for event in market_events if event.get('type') == 'market_source_changed'],
        )
        handover_payload['open_issues'] = status['open_issues']
        handover_payload['research_handoffs_due'] = status['research_handoffs_due']
        self.handover.save(handover_payload)

        document_results = self._sync_managed_documents(status)
        truth_result = self._reconcile_document_truth(status)
        status['runtime_truth'] = {
            'strategy': truth_result.get('strategy'),
            'unresolved_stale_claims': len(truth_result.get('unresolved_stale_current_claims', [])),
            'superseded_stale_claims': len(truth_result.get('superseded_stale_current_claims', [])),
            'provenance': truth_result.get('provenance', {}),
        }
        atomic_write_json(self.root / 'state' / 'runtime_truth.json', truth_result)

        self._queue_new_direct_events(checks, pending_decisions, now=now)
        deliveries = self._dispatch_outbox()

        heartbeat = {
            'schema': 1,
            'service': 'energie-projectmanager-v2',
            'state': 'waiting',
            'heartbeat_at': now.isoformat(),
            'health': health['status'],
            'mode': status['mode'],
            'pending_decisions': len(pending_decisions),
            'pending_notifications': len(self.outbox.pending()),
        }
        atomic_write_json(self.root / 'heartbeat' / 'manager.json', heartbeat)
        self.audit.write('manager.run', actor='projectmanager', result='ok', details={
            'health': health['status'],
            'attention_count': health['attention_count'],
            'mode': status['mode'],
            'delivery_count': len(deliveries),
            'market_event_count': len(market_events),
            'research_event_count': len(research_events),
            'document_changes': sum(1 for item in document_results if item.get('changed')),
            'runtime_truth_unresolved': len(truth_result.get('unresolved_stale_current_claims', [])),
            'retention_deleted': len(retention_result.get('deleted', [])),
        })
        self_audit = self.self_auditor.run(now=now)
        atomic_write_json(self.root / 'self_audit' / 'current.json', self_audit)
        status['self_audit'] = self_audit
        status['open_issues'] = self.issues.open_items()
        atomic_write_json(self.root / 'status' / 'current.json', status)
        return status

    def _reconcile_mode(self, runtime: dict):
        runtime_mode = (runtime.get('operating_mode') or {}).get('effective_mode')
        if runtime_mode not in {'USER', 'DEVELOPMENT', 'MAINTENANCE'}:
            return
        current_mode = self.mode.get().get('mode')
        if current_mode != runtime_mode:
            self.mode.set(runtime_mode, reason='authoritative_runtime_reconciliation', source='runtime')
            self.audit.write(
                'mode.reconciled',
                actor='projectmanager',
                result='ok',
                details={'from': current_mode, 'to': runtime_mode},
            )

    def _record_evidence(self, checks):
        for check in checks:
            verified = (
                check.get('evidence_strength') == 'verified'
                and bool(check.get('evidence_ref'))
            )
            self.evidence.upsert_current(
                check.get('name', 'health'),
                'BEWEZEN' if verified else 'NOG_TE_CONTROLEREN',
                source='manager_health',
                evidence_ref=check.get('evidence_ref') if verified else None,
                details={'result': check.get('status'), 'reason': check.get('reason')},
            )

    def _reconcile_issues(self, checks: list, market_events: list):
        for check in checks:
            fingerprint = f"health:{check.get('name')}"
            if check.get('status') == 'GREEN':
                self.issues.resolve_fingerprint(fingerprint, resolution='health check returned GREEN')
            else:
                self.issues.open(
                    fingerprint,
                    severity=check.get('status', 'ORANGE'),
                    title=check.get('name', 'health issue'),
                    details={'reason': check.get('reason'), 'evidence_ref': check.get('evidence_ref')},
                )
        for event in market_events:
            if event.get('type') == 'market_source_error':
                self.issues.open(
                    f"market:{event.get('source_id')}",
                    severity='ORANGE',
                    title=f"Market source unavailable: {event.get('source_id')}",
                    details={'detail': event.get('detail')},
                )
            else:
                self.issues.resolve_fingerprint(
                    f"market:{event.get('source_id')}",
                    resolution='official market source checked successfully',
                )
                if event.get('type') == 'market_source_changed':
                    self.opportunities.upsert(
                        f"market:{event.get('source_id')}:{event.get('sha256')}",
                        category=event.get('category') or 'market',
                        subject=f"Wijziging bij {event.get('source_id')}",
                        evidence=[event.get('evidence_ref')] if event.get('evidence_ref') else [],
                        details={'source_id': event.get('source_id'), 'sha256': event.get('sha256')},
                    )

    def _reconcile_research(self, market_events, *, now):
        events = []
        by_source = {
            event.get('source_id'): event
            for event in market_events
            if event.get('type') in {'market_source_changed', 'market_source_checked'}
            and event.get('evidence_ref')
        }
        for item in self.research.due(now=now, executor='official_monitor'):
            matching = next((by_source.get(source_id) for source_id in item.get('source_ids', []) if by_source.get(source_id)), None)
            if not matching:
                continue
            completed = self.research.complete(item['key'], evidence_ref=matching['evidence_ref'], now=now)
            events.append({
                'type': 'research_completed',
                'key': item['key'],
                'source_id': matching.get('source_id'),
                'evidence_ref': matching.get('evidence_ref'),
                'next_due': completed.get('due_at'),
            })
        return events

    def _maybe_select_roadmap_task(self, health: dict, pending_decisions: list):
        if self.tasks.active() is not None or pending_decisions:
            return None
        if health.get('status') == 'RED':
            return None
        item = self.roadmap.next_open()
        if not item:
            return None
        next_action = f"handoff:{item['key']} — {item['title']}"
        task = self.tasks.start(
            item['title'],
            item['title'],
            mode=item.get('mode', 'USER'),
            steps_total=1,
            priority=int(item.get('priority', 5)),
        )
        task = self.tasks.progress(task['id'], next_action=next_action)
        self.roadmap.mark_active(item['key'], task['id'])
        self.audit.write(
            'roadmap.task.selected',
            actor='projectmanager',
            result='ok',
            details={'roadmap_key': item['key'], 'task_id': task['id'], 'executor': item.get('executor')},
        )
        return {'key': item['key'], 'task_id': task['id'], 'executor': item.get('executor'), 'next_action': next_action}

    def _apply_safe_retention(self, *, now):
        candidates = retention_candidates(self.root, now=now, keep_days=30)
        if not candidates:
            return {'deleted': [], 'blocked': False, 'candidates': 0}
        result = apply_retention(self.root, now=now, keep_days=30, confirmed_owned_scope=True)
        result['candidates'] = len(candidates)
        if result.get('deleted'):
            self.audit.write(
                'retention.applied',
                actor='projectmanager',
                result='ok',
                details={'count': len(result['deleted'])},
            )
        return result

    def _document_paths(self):
        kb_dir = Path(self.config.reports_root) / 'KnowledgeBase'
        return [
            kb_dir / 'ACTUELE_STATUS.md',
            kb_dir / 'EnergieProject_Roadmap.md',
            kb_dir / 'Knowledge_Base_Master_Index.md',
        ]

    def _reconcile_document_truth(self, status: dict):
        result = evaluate_runtime_first(
            self._document_paths(),
            release=status.get('release', {}).get('version') or '',
            mode=status.get('mode') or '',
            health=status.get('health', {}).get('status') or '',
        )
        fingerprint = 'document_truth:runtime_first'
        unresolved = result.get('unresolved_stale_current_claims', [])
        if unresolved:
            self.issues.open(
                fingerprint,
                severity='ORANGE',
                title='Actuele documentclaims conflicteren nog met runtime truth',
                details={'claims': unresolved[:20]},
            )
        else:
            self.issues.resolve_fingerprint(
                fingerprint,
                resolution='runtime truth is authoritative and visible at document top',
            )
        return result

    def _queue_new_direct_events(self, checks: list, decisions: list, *, now):
        for check in checks:
            if check.get('status') != 'RED':
                continue
            event = {
                'severity': 'RED',
                'subject': f"Energie PM — {check.get('name')}",
                'detail': check.get('reason', 'rood'),
                'fingerprint': f"health:{check.get('name')}:{check.get('reason')}",
            }
            if self.alerts.should_send(event, now=now):
                route_event(self.outbox, event)
                self.alerts.mark_sent(event, now=now)
                self.audit.write('notification.queued', actor='projectmanager', result='ok', details={'fingerprint': event['fingerprint']})

        for decision in decisions:
            event = {
                'severity': 'ORANGE',
                'peter_decision_needed': True,
                'subject': 'Energie PM — beslissing nodig',
                'detail': decision.get('question', decision.get('kind', 'beslissing nodig')),
                'decision_id': decision.get('id'),
                'fingerprint': f"decision:{decision.get('id')}",
            }
            if self.alerts.should_send(event, now=now):
                route_event(self.outbox, event)
                self.alerts.mark_sent(event, now=now)
                self.audit.write('decision.notification.queued', actor='projectmanager', result='ok', details={'decision_id': decision.get('id')})

    def _dispatch_outbox(self):
        deliveries = []
        for path, payload in self.outbox.pending():
            result = self.notifier.send(
                payload.get('subject', 'Energie Projectmanager'),
                payload.get('detail', ''),
                severity=payload.get('severity', 'RED'),
                notification_id=f"energie_projectmanager_{payload.get('id', 'alert')}",
            )
            deliveries.append({'path': str(path), 'result': result})
            if result.get('ok') is True:
                self.outbox.mark_delivered(path, result)
                self.audit.write('notification.delivered', actor='projectmanager', result='ok', details={'transport': result.get('transport')})
            else:
                self.audit.write('notification.delivery_failed', actor='projectmanager', result='deferred', details={'reason': result.get('reason')})
        return deliveries

    def _sync_managed_documents(self, status: dict):
        kb_dir = Path(self.config.reports_root) / 'KnowledgeBase'
        if not kb_dir.exists():
            return []
        task = status.get('active_task') or {}
        decisions = status.get('decisions_needed') or []
        issues = status.get('open_issues') or []
        release = status.get('release', {}).get('version') or 'NOG_TE_CONTROLEREN'
        mode = status.get('mode') or 'NOG_TE_CONTROLEREN'
        health = status.get('health', {}).get('status') or 'NOG_TE_CONTROLEREN'
        truth_header = [
            '## Projectmanager V2 — ACTUELE RUNTIME WAARHEID',
            f'- PMV2 runtime truth: **{release} | {mode} | {health}**',
            '- Deze runtime-sectie is leidend voor actuele status; oudere statusclaims verderop zijn historische audit/context tenzij expliciet opnieuw gevalideerd.',
        ]
        status_content = '\n'.join(truth_header + [
            f"- Actieve taak: {task.get('title') or 'geen'}",
            f"- Stap: {task.get('step') or '-'} / {task.get('steps_total') or '-'}",
            f"- Volgende actie: {task.get('next_action') or 'geen'}",
            f"- Open issues: {len(issues)}",
            f"- Peter nodig: {'ja' if decisions else 'nee'}",
        ])
        roadmap_content = '\n'.join(truth_header + [
            '## Projectmanager actieve regie',
            f"- Actieve taak: {task.get('title') or 'geen'}",
            f"- Status: {task.get('status') or 'geen actieve taak'}",
            f"- Volgende actie: {task.get('next_action') or 'geen'}",
            f"- Open beslissingen: {len(decisions)}",
            f"- Open issues: {len(issues)}",
        ])
        master_content = '\n'.join(truth_header + [
            '## Projectmanager V2 runtime-ingangen',
            '- Actuele status: `ACTUELE_STATUS.md`',
            '- Roadmap: `EnergieProject_Roadmap.md`',
            '- Runtime truth en handover: `Inbox/projectmanager_v2/RuntimeV2/`',
            '- Externe commandvoorstellen: `Data/03_Systeem/Projectmanager/CommandIngress/`; alleen de embedded PM schrijft RuntimeV2.',
            '- Nomad gebruikt dezelfde Projectmanager-truth; geen parallelle projectwaarheid.',
        ])
        return [
            self.document_sync.update(kb_dir / 'ACTUELE_STATUS.md', 'PROJECTMANAGER_V2', status_content, placement='top'),
            self.document_sync.update(kb_dir / 'EnergieProject_Roadmap.md', 'PROJECTMANAGER_V2', roadmap_content, placement='top'),
            self.document_sync.update(kb_dir / 'Knowledge_Base_Master_Index.md', 'PROJECTMANAGER_V2', master_content, placement='top'),
        ]
