from datetime import datetime, timezone
from pathlib import Path

from operating_mode import ModeStore
from research_queue import ResearchQueue
from task_engine import TaskStore

DEFAULT_RESEARCH_TOPICS = (
    ('battery-market', 'battery', 5, 30, 'thuisbatterij markt Marstek Venus 3 alternatieven business case'),
    ('energy-regulation', 'regulation', 2, 14, 'Nederland energie regelgeving saldering netkosten belastingen'),
    ('supplier-tariffs', 'supplier', 3, 14, 'Nederland energiecontracten dynamisch vast terugleverkosten NextEnergy'),
    ('home-assistant-security', 'security', 1, 14, 'Home Assistant security advisories EnergieProject'),
    ('nas-lifecycle', 'end_of_life', 3, 30, 'QNAP TS-453Be lifecycle security updates end of life'),
    ('ai-vendor-lockin', 'continuity', 4, 30, 'AI tooling vendor lock-in lower-cost local fallback project manager'),
    ('energy-data-quality', 'data_quality', 2, 7, 'energie brondata kwaliteit HomeWizard Enphase SlimmeMeterPortal Nordpool'),
    ('energy-hardware', 'hardware', 5, 30, 'energy management hardware inverter solar EV charger heat pump innovations'),
)


def bootstrap_runtime(runtime_root, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    root = Path(runtime_root)
    root.mkdir(parents=True, exist_ok=True)

    mode_store = ModeStore(root / 'state' / 'mode.json')
    mode = mode_store.get()
    if mode.get('updated_at') is None:
        mode = mode_store.set('DEVELOPMENT', reason='projectmanager_v2_build_active', source='bootstrap')

    tasks = TaskStore(root / 'state' / 'tasks.json')
    existing = tasks._load().get('tasks', [])
    pm_tasks = [item for item in existing if item.get('title') == 'Energie Projectmanager V2 bouwen']
    if pm_tasks:
        task = pm_tasks[-1]
    else:
        task = tasks.start(
            'Energie Projectmanager V2 bouwen',
            'Complete autonome Energie Projectmanager bouwen, testen en releaseklaar maken',
            mode='DEVELOPMENT', steps_total=12, priority=2,
        )
        tasks.progress(task['id'], step=9, next_action='24/7 service en integratietesten afronden')
        task = tasks.active()

    research = ResearchQueue(root / 'opportunities' / 'research_queue.json')
    for key, category, priority, cadence_days, query in DEFAULT_RESEARCH_TOPICS:
        try:
            research.get(key)
        except KeyError:
            research.upsert(key, category, due_at=now, priority=priority, cadence_days=cadence_days, query=query)

    return {'mode': mode, 'active_task': task, 'research_topics': len(research._load().get('items', []))}
