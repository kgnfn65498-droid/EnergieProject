import argparse
import compileall
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cr_evidence import evaluate_cr_closure
from health_engine import evaluate_quarter_hour_heartbeat
from manager_config import ManagerConfig
from manager_service import ManagerService

BASE = Path(__file__).resolve().parent


def run_unit_tests():
    suite = unittest.defaultTestLoader.discover(str(BASE / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'ok': result.wasSuccessful()}


def compile_sources():
    ok = compileall.compile_dir(str(BASE), quiet=1, force=True)
    return {'ok': bool(ok)}


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def live_probe(project_root, input_root):
    now = datetime.now(timezone.utc)
    heartbeat_path = Path(input_root) / '_scheduler' / 'quarter_hour_heartbeat.json'
    cr_dir = Path(project_root) / 'Data' / '03_Systeem' / 'Projectmanager' / 'State'
    cr_files = sorted(cr_dir.glob('crash_recovery_closure_*.json'))
    version_path = Path(project_root) / 'App' / 'VERSIE.txt'
    mode_path = Path(project_root) / 'Inbox' / 'operating_mode' / 'operating_mode_state.json'
    probe = {'heartbeat_path': str(heartbeat_path), 'cr_path': str(cr_files[-1]) if cr_files else None, 'version_path': str(version_path), 'mode_path': str(mode_path)}
    probe['heartbeat'] = evaluate_quarter_hour_heartbeat(_read_json(heartbeat_path), now=now) if heartbeat_path.is_file() else {'status':'RED','reason':'missing'}
    probe['cr'] = evaluate_cr_closure(_read_json(cr_files[-1])) if cr_files else {'status':'ORANGE','reason':'missing'}
    probe['version'] = version_path.read_text(encoding='utf-8').strip() if version_path.is_file() else None
    probe['mode'] = _read_json(mode_path) if mode_path.is_file() else None
    probe['ok'] = probe['heartbeat'].get('status') == 'GREEN' and probe['cr'].get('status') == 'GREEN' and bool(probe['version']) and isinstance(probe['mode'], dict)
    return probe


def one_shot_integration(project_root, input_root, recovery_root):
    class NoopNotifier:
        def send(self, *args, **kwargs):
            return {'ok': False, 'reason': 'acceptance_no_delivery'}

    with tempfile.TemporaryDirectory(prefix='pmv2-accept-') as td:
        root = Path(td)
        reports = root / 'reports'
        (reports / 'KnowledgeBase').mkdir(parents=True)
        for name in ('ACTUELE_STATUS.md','EnergieProject_Roadmap.md','Knowledge_Base_Master_Index.md'):
            (reports / 'KnowledgeBase' / name).write_text(f'# {name}\n', encoding='utf-8')
        cfg = ManagerConfig(
            project_root=str(project_root), system_root=str(root / 'runtime'), input_root=str(input_root),
            recovery_root=str(recovery_root), reports_root=str(reports), interval_seconds=300,
            timezone='Europe/Amsterdam', ha_base_url='', ha_token='', ha_notify_service='', market_enabled=False,
        )
        status = ManagerService(cfg, notifier=NoopNotifier()).run_once()
        required = [root/'runtime/status/current.json', root/'runtime/heartbeat/manager.json', root/'runtime/handover/current.json', root/'runtime/audit/events.jsonl']
        return {
            'ok': all(path.is_file() for path in required) and status.get('mode') in {'USER','DEVELOPMENT','MAINTENANCE'},
            'mode': status.get('mode'),
            'health': (status.get('health') or {}).get('status'),
            'required_runtime_files': {str(path.name): path.is_file() for path in required},
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', default=os.getenv('PM_PROJECT_ROOT','/project'))
    parser.add_argument('--input-root', default=os.getenv('PM_INPUT_ROOT','/input'))
    parser.add_argument('--recovery-root', default=os.getenv('PM_RECOVERY_ROOT','/recovery'))
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    report = {
        'schema': 'energie_projectmanager_v2_acceptance_v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'compile': compile_sources(),
        'unit_tests': run_unit_tests(),
    }
    if Path(args.project_root).exists() and Path(args.input_root).exists():
        report['live_probe'] = live_probe(args.project_root, args.input_root)
        report['integration'] = one_shot_integration(args.project_root, args.input_root, args.recovery_root)
    else:
        report['live_probe'] = {'ok': False, 'skipped': True, 'reason': 'live_mounts_not_available'}
        report['integration'] = {'ok': False, 'skipped': True, 'reason': 'live_mounts_not_available'}
    report['ok'] = all([
        report['compile']['ok'], report['unit_tests']['ok'],
        report['live_probe'].get('ok') is True, report['integration'].get('ok') is True,
    ])
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    print(text)
    if args.output:
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(text, encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
