from pathlib import Path

REQUIRED_RUNTIME_FILES = (
    'status/current.json',
    'heartbeat/manager.json',
    'handover/current.json',
    'audit/events.jsonl',
)


class SelfAuditor:
    def __init__(self, runtime_root):
        self.root = Path(runtime_root)

    def run(self) -> dict:
        missing = [rel for rel in REQUIRED_RUNTIME_FILES if not (self.root / rel).is_file()]
        return {
            'status': 'GREEN' if not missing else 'ORANGE',
            'missing': missing,
            'required_files': list(REQUIRED_RUNTIME_FILES),
        }
