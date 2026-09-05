from datetime import datetime, timezone
from pathlib import Path

from operating_mode import ModeStore
from research_queue import ResearchQueue
from roadmap_regie import RoadmapRegie
from task_engine import TaskStore

# Only topics with a real bounded official-source monitor may self-complete.
# Broader market/strategy topics remain handoff research and never create a
# false health failure merely because the embedded PM cannot browse the web.
DEFAULT_RESEARCH_TOPICS = (
    ('home-assistant-security', 'security', 1, 14, 'Home Assistant security advisories EnergieProject', 'official_monitor', ('home_assistant_security', 'home_assistant_alerts')),
    ('energy-regulation', 'regulation', 2, 14, 'Nederland energie regelgeving saldering netkosten belastingen', 'official_monitor', ('acm_energy_news', 'rijksoverheid_saldering')),
    ('qnap-security', 'security', 1, 14, 'QNAP security advisories TS-453Be', 'official_monitor', ('qnap_security',)),
    ('battery-market', 'battery', 5, 30, 'thuisbatterij markt Marstek HomeWizard Anker business case', 'handoff', ()),
    ('supplier-tariffs', 'supplier', 3, 14, 'Nederland energiecontracten dynamisch vast terugleverkosten NextEnergy', 'handoff', ()),
    ('ai-vendor-lockin', 'continuity', 4, 30, 'AI tooling vendor lock-in lower-cost local fallback project manager', 'handoff', ()),
    ('energy-data-quality', 'data_quality', 2, 7, 'energie brondata kwaliteit HomeWizard Enphase SlimmeMeterPortal Nordpool', 'handoff', ()),
    ('energy-hardware', 'hardware', 5, 30, 'energy management hardware inverter solar EV charger heat pump innovations', 'handoff', ()),
)


def bootstrap_runtime(runtime_root, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    root = Path(runtime_root)
    root.mkdir(parents=True, exist_ok=True)

    mode_store = ModeStore(root / 'state' / 'mode.json')
    mode = mode_store.get()
    if mode.get('updated_at') is None:
        mode = mode_store.set('USER', reason='neutral_runtime_bootstrap', source='bootstrap')

    tasks = TaskStore(root / 'state' / 'tasks.json')
    active = tasks.active()

    research = ResearchQueue(root / 'opportunities' / 'research_queue.json')
    for key, category, priority, cadence_days, query, executor, source_ids in DEFAULT_RESEARCH_TOPICS:
        try:
            research.get(key)
        except KeyError:
            research.upsert(
                key,
                category,
                due_at=now,
                priority=priority,
                cadence_days=cadence_days,
                query=query,
                executor=executor,
                source_ids=source_ids,
            )

    roadmap = RoadmapRegie(root / 'roadmap' / 'queue.json')
    roadmap.seed_defaults(now=now)

    return {
        'mode': mode,
        'active_task': active,
        'research_topics': len(research.all()),
        'roadmap_items': len(roadmap.all()),
        'bootstrap_semantics': 'neutral_production_recovery',
    }
