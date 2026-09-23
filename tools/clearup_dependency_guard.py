#!/usr/bin/env python3
from pathlib import Path
import sys
needles=[".bridge_patch_stage_20260914T171141Z","live_bridge_backup_20260914T171141Z","live_bridge_backup_queue_schema_20260914T172223Z",".release-transition.operation.lock.backup_20260914T1812Z"]
root=Path(sys.argv[1]).resolve();hits=[]
for base in [root/"App",root/"tools",root/"slimmemeterportal_import"]:
 if not base.exists():continue
 for p in base.rglob("*"):
  if not p.is_file():continue
  try:t=p.read_text(encoding="utf-8")
  except (UnicodeDecodeError,OSError):continue
  for n in needles:
   if n in t:hits.append((p.relative_to(root).as_posix(),n))
if hits:
 for p,n in hits:print("BLOCKED",n,"<-",p)
 raise SystemExit(2)
print("CLEARUP_001_DEPENDENCY_GUARD_GREEN")
