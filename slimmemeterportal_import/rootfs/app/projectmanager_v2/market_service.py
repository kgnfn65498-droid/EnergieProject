from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_monitor import SourceMonitor
from persistence import atomic_write_json, load_json
from source_catalog import OFFICIAL_SOURCES


class NullMarketService:
    def run_due(self, *, now=None) -> list:
        return []


class MarketService:
    def __init__(self, runtime_root, *, sources=None, monitor=None, max_sources_per_cycle: int = 1):
        self.root = Path(runtime_root)
        self.sources = list(sources or OFFICIAL_SOURCES)
        self.schedule_path = self.root / 'market_schedule.json'
        self.monitor = monitor or SourceMonitor(self.root / 'market_sources.json')
        self.max_sources_per_cycle = max(1, int(max_sources_per_cycle))

    def _load_schedule(self):
        return load_json(self.schedule_path, default={'schema':1,'next_due':{}})

    def run_due(self, *, now=None) -> list:
        now = now or datetime.now(timezone.utc)
        schedule = self._load_schedule()
        events = []
        checked = 0
        for source in sorted(self.sources, key=lambda x: (x.get('priority',99), x['id'])):
            due_raw = schedule.get('next_due', {}).get(source['id'])
            due = None
            if due_raw:
                try:
                    due = datetime.fromisoformat(due_raw.replace('Z','+00:00'))
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    due = None
            if due is not None and due > now:
                continue
            if checked >= self.max_sources_per_cycle:
                break
            checked += 1
            try:
                result = self.monitor.check(source)
                if result.get('changed') and result.get('relevant'):
                    events.append({
                        'type': 'market_source_changed',
                        'severity': 'ORANGE',
                        'category': source.get('category'),
                        'source_id': source['id'],
                        'subject': source['id'],
                        'evidence_ref': result.get('evidence_ref'),
                        'sha256': result.get('sha256'),
                        'priority': source.get('priority', 5),
                    })
            except Exception as exc:
                events.append({
                    'type': 'market_source_error',
                    'severity': 'ORANGE',
                    'category': source.get('category'),
                    'source_id': source['id'],
                    'subject': source['id'],
                    'detail': f'{type(exc).__name__}: {exc}',
                    'priority': source.get('priority', 5),
                })
            cadence = max(1, int(source.get('cadence_hours', 24)))
            schedule.setdefault('next_due', {})[source['id']] = (now + timedelta(hours=cadence)).isoformat()
        atomic_write_json(self.schedule_path, schedule)
        return events
