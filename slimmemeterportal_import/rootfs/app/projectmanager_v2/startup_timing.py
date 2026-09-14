from __future__ import annotations
import json,os,time
from datetime import datetime,timezone
from pathlib import Path
class StartupTiming:
    def __init__(self, project_root):
        self.start=time.monotonic(); self.path=Path(project_root)/'Inbox/projectmanager_v2/RuntimeV2/startup_timing/current.json'; self.phases=[]
    def mark(self, phase):
        self.phases.append({'phase':str(phase),'elapsed_monotonic_seconds':round(time.monotonic()-self.start,6),'observed_at':datetime.now(timezone.utc).isoformat()})
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps({'schema':'energie_startup_timing_v1','phases':self.phases},indent=2)+'\n'); os.replace(tmp,self.path)
        return self.phases[-1]
