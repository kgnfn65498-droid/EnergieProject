#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
DEFAULT_ITEMS=["Inbox/.bridge_patch_stage_20260914T171141Z","Inbox/live_bridge_backup_20260914T171141Z","Inbox/live_bridge_backup_queue_schema_20260914T172223Z","Inbox/.release-transition.operation.lock.backup_20260914T1812Z"]
NEEDLES=[Path(x).name for x in DEFAULT_ITEMS]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for c in iter(lambda:f.read(1048576),b""):h.update(c)
 return h.hexdigest()
def safe(root,rel):
 p=(root/rel).resolve()
 if p==root or root not in p.parents:raise RuntimeError("unsafe path "+rel)
 return p
def deps(root):
 hits=[]
 for base in [root/"App",root/"tools",root/"slimmemeterportal_import"]:
  if not base.exists():continue
  for p in base.rglob("*"):
   if not p.is_file():continue
   try:t=p.read_text(encoding="utf-8")
   except (UnicodeDecodeError,OSError):continue
   for n in NEEDLES:
    if n in t:hits.append([p.relative_to(root).as_posix(),n])
 return hits
def collect(root,rels):
 rows=[]
 for rel in rels:
  p=safe(root,rel)
  if not p.exists() or p.is_symlink():raise RuntimeError("candidate missing/unsafe "+rel)
  seq=[p] if p.is_file() else [p,*sorted(p.rglob("*"))]
  for q in seq:
   if q.is_symlink():raise RuntimeError("symlink refused")
   r=q.relative_to(root).as_posix()
   if q.is_file():rows.append({"path":r,"type":"file","size":q.stat().st_size,"sha256":sha(q)})
   elif q.is_dir():rows.append({"path":r,"type":"directory"})
 return rows
def verify(zp):
 with zipfile.ZipFile(zp) as z:
  if z.testzip():raise RuntimeError("corrupt recovery ZIP")
  m=json.loads(z.read("CLEARUP_MANIFEST.json"))
  for x in m["items"]:
   if x["type"]=="file" and hashlib.sha256(z.read(x["path"])).hexdigest()!=x["sha256"]:raise RuntimeError("archive hash mismatch")
 return m
def prepare(a):
 root=Path(a.project).resolve();out=Path(a.output).resolve()
 if root==out or root in out.parents:raise RuntimeError("recovery ZIP must be outside project")
 if deps(root):raise RuntimeError("dependency guard RED")
 rows=collect(root,a.item);m={"schema":1,"clearup_id":a.id,"created_at":datetime.now(timezone.utc).isoformat(),"classification":"TYPE1","roots":a.item,"items":rows,"deletion_performed":False}
 out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix(out.suffix+".tmp")
 with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:
  z.writestr("CLEARUP_MANIFEST.json",json.dumps(m,indent=2))
  for x in rows:
   p=root/x["path"]
   if x["type"]=="directory":z.writestr(x["path"].rstrip("/")+"/",b"")
   else:z.write(p,x["path"])
 os.replace(tmp,out);verify(out)
 print(json.dumps({"status":"PREPARED","zip":str(out),"sha256":sha(out),"confirmation_token":"CONFIRM_DELETE_"+a.id},indent=2))
def apply(a):
 root=Path(a.project).resolve();zp=Path(a.recovery).resolve()
 if a.confirm!="CONFIRM_DELETE_"+a.id:raise RuntimeError("exact confirmation required")
 if deps(root):raise RuntimeError("dependency guard RED immediately before delete")
 m=verify(zp)
 if m.get("clearup_id")!=a.id or m.get("roots")!=a.item:raise RuntimeError("manifest contract mismatch")
 expected={(x["path"],x["type"]):(x.get("size"),x.get("sha256")) for x in m["items"]}
 live=collect(root,a.item);actual={(x["path"],x["type"]):(x.get("size"),x.get("sha256")) for x in live}
 if actual!=expected:raise RuntimeError("live tree changed since prepare")
 for rel in a.item:
  p=safe(root,rel)
  if p.is_dir():shutil.rmtree(p)
  elif p.is_file():p.unlink()
  else:raise RuntimeError("candidate disappeared")
 if any(safe(root,r).exists() for r in a.item):raise RuntimeError("readback failed")
 print(json.dumps({"status":"CLEANUP_GREEN","removed":a.item},indent=2))
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True)
 x=s.add_parser("prepare");x.add_argument("--project",required=True);x.add_argument("--output",required=True);x.add_argument("--id",default="ClearUp_001");x.add_argument("--item",action="append",default=[]);x.set_defaults(fn=prepare)
 x=s.add_parser("apply");x.add_argument("--project",required=True);x.add_argument("--recovery",required=True);x.add_argument("--confirm",required=True);x.add_argument("--id",default="ClearUp_001");x.add_argument("--item",action="append",default=[]);x.set_defaults(fn=apply)
 a=p.parse_args()
 if not a.item:a.item=list(DEFAULT_ITEMS)
 a.fn(a)
if __name__=="__main__":main()
