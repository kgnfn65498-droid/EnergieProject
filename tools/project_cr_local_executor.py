#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUEST_SCHEMA='energie_project_cr_local_request_v1'
RESULT_SCHEMA='energie_project_cr_local_result_v1'
OPERATION='project_cr_create'
REQUEST_ID=re.compile(r'^[0-9a-f]{32}$')


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    try:
        tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)


def execute(root: Path) -> dict:
    root=Path(root).resolve(); bridge=root/'Inbox/project_cr_local'
    request_path=bridge/'request.json'; result_path=bridge/'result.json'
    req=None
    try:
        if request_path.is_symlink() or result_path.is_symlink(): raise RuntimeError('onveilig bridgepad')
        req=json.loads(request_path.read_text(encoding='utf-8'))
        if req.get('schema')!=REQUEST_SCHEMA or req.get('operation')!=OPERATION or not REQUEST_ID.fullmatch(str(req.get('request_id') or '')):
            raise RuntimeError('ongeldig EnergieProject CR request')
        command_id = str(req.get('command_id') or '').strip()
        if command_id and not REQUEST_ID.fullmatch(command_id):
            raise RuntimeError('ongeldig EnergieProject CR command_id')
        version=(root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
        if req.get('expected_runtime_version')!=version: raise RuntimeError('runtimeversie gewijzigd sinds request')
        native=root/'Infra/Docker/native-mcp'
        sys.path.insert(0,str(native))
        from crash_recovery import create_crash_recovery_backup, verify_crash_recovery_backup
        created=create_crash_recovery_backup(root,root/'Backups',retention=1)
        verify=verify_crash_recovery_backup(root/'Backups',created.get('backup_name'),deep_verify_files=True)
        expected_suffix=f' {version} CR EnergieProject.zip'
        if created.get('status')!='valid' or created.get('deep_verified') is not True or verify.get('status')!='valid':
            raise RuntimeError('EnergieProject CR verificatie RED')
        if not str(created.get('backup_name') or '').endswith(expected_suffix):
            raise RuntimeError('EnergieProject CR naam/runtimeversie mismatch')
        if created.get('retention_delete_performed') not in (None,False):
            raise RuntimeError('EnergieProject CR rapporteert onverwachte delete')
        result={'schema':RESULT_SCHEMA,'request_id':req['request_id'],'operation':OPERATION,'status':'GREEN','ok':True,
                'version':version,'backup_name':created.get('backup_name'),'backup_sha256':created.get('backup_sha256'),
                'deep_verified':True,'verified_files':verify.get('verified_files'),'retention':1,
                'retention_quarantined':created.get('retention_quarantined',[]),'delete_performed':False,
                'finished_at':datetime.now(timezone.utc).isoformat()}
        if command_id:
            result['command_id'] = command_id
        _write(result_path,result); return result
    except Exception as exc:
        result={
            'schema':RESULT_SCHEMA,
            'request_id':req.get('request_id') if isinstance(req,dict) else None,
            'operation':OPERATION,
            'status':'RED',
            'ok':False,
            'error':str(exc),
            'finished_at':datetime.now(timezone.utc).isoformat(),
        }
        failed_command_id = str(req.get('command_id') or '').strip() if isinstance(req, dict) else ''
        if REQUEST_ID.fullmatch(failed_command_id):
            result['command_id'] = failed_command_id
        try:
            _write(result_path,result)
        except Exception:
            pass
        raise
    finally:
        # Consume only the exact request handled by this invocation. The result
        # stays as evidence. This prevents the watcher loop from rebuilding the
        # same Crash Recovery set every maintenance cycle.
        if isinstance(req, dict) and request_path.is_file() and not request_path.is_symlink():
            try:
                current=json.loads(request_path.read_text(encoding='utf-8'))
                if current.get('request_id') == req.get('request_id'):
                    request_path.unlink()
            except (OSError, json.JSONDecodeError, AttributeError):
                pass


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); args=ap.parse_args()
    try:
        print(json.dumps(execute(Path(args.root)),ensure_ascii=False,sort_keys=True)); return 0
    except Exception as exc:
        print(f'PROJECT_CR_LOCAL_EXECUTOR_RED: {exc}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
