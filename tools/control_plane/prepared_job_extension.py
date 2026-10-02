from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ACTION = "prepared_job_run"
REQUEST_SCHEMA = "energie_prepared_job_request_v2"
AUTH_SCHEMA = "energie_prepared_job_authorization_v1"
MANIFEST_SCHEMA = "energie_prepared_job_manifest_v1"
RESULT_SCHEMA = "energie_prepared_job_result_v2"
IMAGE = "energie-filesystem-mcp:runtime-v1"
CONTROL_PLANE_CONTAINER = "energie-control-plane"
CONTROL_PLANE_SUFFIX = "/Data/03_Systeem/Projectmanager/ControlPlane"
OPERATIONS = {"AUDIT": 3600, "TEST": 10800, "BUILD": 14400}
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+$")
RECEIPT_PREFIX = "ENERGIE_PREPARED_JOB_RECEIPT="

BOOTSTRAP = r"""
import hashlib,json,os,pathlib
job=pathlib.Path("/job")
project=pathlib.Path("/project")
runner=job/"runner.py"
request_id=os.environ["ENERGIE_PREPARED_JOB_REQUEST_ID"]
operation=os.environ["ENERGIE_PREPARED_JOB_OPERATION"]
expected=os.environ["ENERGIE_PREPARED_JOB_RUNNER_SHA256"]
manifest_sha=os.environ["ENERGIE_PREPARED_JOB_MANIFEST_SHA256"]
predecessor_sha=os.environ["ENERGIE_PREPARED_JOB_PREDECESSOR_SHA256"]

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

if not project.is_dir():
    raise RuntimeError("project mount missing")
if runner.is_symlink() or not runner.is_file():
    raise RuntimeError("runner missing/unsafe")
if sha(runner)!=expected:
    raise RuntimeError("runner sha mismatch")
manifest=job/"job_manifest.json"
if manifest.is_symlink() or not manifest.is_file() or sha(manifest)!=manifest_sha:
    raise RuntimeError("manifest identity mismatch")
manifest_payload=json.loads(manifest.read_text(encoding="utf-8"))
expected_manifest={
    "schema":"energie_prepared_job_manifest_v1",
    "request_id":request_id,
    "task_id":os.environ["ENERGIE_PREPARED_JOB_TASK_ID"],
    "operation":operation,
    "target_release":os.environ["ENERGIE_PREPARED_JOB_TARGET_RELEASE"],
    "predecessor_release":os.environ["ENERGIE_PREPARED_JOB_PREDECESSOR_RELEASE"],
    "predecessor_sha256":predecessor_sha,
    "runner_sha256":expected,
}
if manifest_payload!=expected_manifest:
    raise RuntimeError("manifest content mismatch")
predecessor=project/"Data/03_Systeem/Projectmanager/ReleaseArtifacts"/("EnergieProject_v"+expected_manifest["predecessor_release"]+".zip")
if predecessor.is_symlink() or not predecessor.is_file() or sha(predecessor)!=predecessor_sha:
    raise RuntimeError("predecessor artifact identity mismatch")

probe=job/(".write_probe_"+request_id)
fd=os.open(str(probe),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
try:
    with os.fdopen(fd,"wb") as f:
        f.write(b"prepared-job-write-readback\n"); f.flush(); os.fsync(f.fileno())
    if probe.read_bytes()!=b"prepared-job-write-readback\n":
        raise RuntimeError("job write/readback mismatch")
finally:
    try: probe.unlink()
    except FileNotFoundError: pass

code=runner.read_bytes()
scope={"__name__":"__main__","__file__":str(runner)}
try:
    exec(compile(code,str(runner),"exec"),scope,scope)
except SystemExit as exc:
    if exc.code not in (None,0):
        raise

if sha(runner)!=expected or sha(manifest)!=manifest_sha:
    raise RuntimeError("job input mutated during execution")

rows=[]
for p in sorted(job.rglob("*")):
    if p.is_symlink():
        raise RuntimeError("symlink output refused:"+p.relative_to(job).as_posix())
    if p.is_dir():
        os.chmod(p,0o755); continue
    if not p.is_file():
        raise RuntimeError("non-regular job output refused:"+p.relative_to(job).as_posix())
    os.chmod(p,0o644)
    rows.append({"path":p.relative_to(job).as_posix(),"size":p.stat().st_size,"sha256":sha(p)})

receipt={
    "schema":"energie_prepared_job_container_receipt_v2",
    "status":"GREEN","request_id":request_id,"operation":operation,
    "runner_sha256":expected,"manifest_sha256":manifest_sha,
    "predecessor_sha256":predecessor_sha,
    "project_mount":"read_only","job_mount":"read_write",
    "network_mode":"none","docker_socket_mounted":False,"outputs":rows,
}
receipt_path=job/"_prepared_job_receipt.json"
receipt_path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
os.chmod(receipt_path,0o644)
print("ENERGIE_PREPARED_JOB_RECEIPT="+json.dumps(receipt,separators=(",",":"),sort_keys=True))
"""

def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("required regular JSON missing/unsafe")
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise RuntimeError("JSON object required")
    return value

def _atomic_json(path: Path, payload: dict, *, mode: int=0o644) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise RuntimeError("result path symlink refused")
    fd,name=tempfile.mkstemp(prefix=f".{path.name}.tmp-",dir=str(path.parent))
    temp=Path(name)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            handle.write(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(temp,mode)
        os.replace(temp,path)
        os.chmod(path,mode)
    finally:
        temp.unlink(missing_ok=True)

def _valid_hex(value: str, regex) -> str:
    value=str(value or "").strip().lower()
    if not regex.fullmatch(value):
        raise RuntimeError("invalid identity field")
    return value

def _load_request(path: Path) -> dict:
    value=_json(path)
    allowed={
        "schema","request_id","action","task_id","operation","target_release",
        "predecessor_release","predecessor_sha256","runner_sha256",
        "manifest_sha256","authorization_sha256",
    }
    if set(value)!=allowed or value.get("schema")!=REQUEST_SCHEMA or value.get("action")!=ACTION:
        raise RuntimeError("prepared job request identity/fields mismatch")
    request_id=_valid_hex(value.get("request_id"),REQUEST_ID_RE)
    operation=str(value.get("operation") or "").upper()
    if operation not in OPERATIONS:
        raise RuntimeError("prepared job operation not allowed")
    task_id=str(value.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError("prepared job task_id missing")
    target=str(value.get("target_release") or "").strip()
    predecessor=str(value.get("predecessor_release") or "").strip()
    if not VERSION_RE.fullmatch(target) or not VERSION_RE.fullmatch(predecessor):
        raise RuntimeError("prepared job release identity invalid")
    return {
        **value,"request_id":request_id,"operation":operation,
        "runner_sha256":_valid_hex(value.get("runner_sha256"),SHA256_RE),
        "predecessor_sha256":_valid_hex(value.get("predecessor_sha256"),SHA256_RE),
        "manifest_sha256":_valid_hex(value.get("manifest_sha256"),SHA256_RE),
        "authorization_sha256":_valid_hex(value.get("authorization_sha256"),SHA256_RE),
    }

def _authorization_fields(request: dict) -> dict:
    return {
        key:request[key] for key in (
            "request_id","task_id","operation","target_release","predecessor_release",
            "predecessor_sha256","runner_sha256","manifest_sha256"
        )
    }

def _claim_authorization(control_plane, request: dict) -> dict:
    name=f"prepared_job_run.{request['request_id']}.json"
    auth=control_plane.result_root/"authorizations"/name
    claim=control_plane.result_root/"claims"/name
    path=claim if claim.is_file() and not claim.is_symlink() else auth
    value=_json(path)
    if value.get("schema")!=AUTH_SCHEMA or value.get("status")!="AUTHORIZED":
        raise RuntimeError("prepared job authorization invalid")
    for key,expected in _authorization_fields(request).items():
        if str(value.get(key) or "")!=str(expected):
            raise RuntimeError("prepared job authorization binding mismatch:"+key)
    expires=float(value.get("expires_at_epoch") or 0)
    if expires<=time.time():
        raise RuntimeError("prepared job authorization expired")
    identity=dict(value); identity.pop("authorization_sha256",None)
    canonical=json.dumps(identity,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    digest=hashlib.sha256(canonical).hexdigest()
    if digest!=request["authorization_sha256"] or digest!=str(value.get("authorization_sha256") or ""):
        raise RuntimeError("prepared job authorization SHA mismatch")
    if path==auth:
        claim.parent.mkdir(parents=True,exist_ok=True)
        if claim.exists():
            raise RuntimeError("prepared job authorization claim conflict")
        os.replace(auth,claim); os.chmod(claim,0o600)
    return value

def _payload(host_project_root: str, request: dict, image_id: str) -> dict:
    host_root=str(host_project_root).rstrip("/")
    allowed={
        "/share/Energie_NAS/EnergieProject",
        "/share/CACHEDEV1_DATA/AI Projecten/EnergieProject",
        "/share/AI Projecten/EnergieProject",
    }
    if host_root not in allowed:
        raise RuntimeError("unexpected host project root")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}",str(image_id or "").lower()):
        raise RuntimeError("prepared job image identity invalid")
    request_id=request["request_id"]; operation=request["operation"]
    job_host=f"{host_root}/Data/03_Systeem/Projectmanager/Staging/PreparedJobs/{request_id}"
    caps=["DAC_OVERRIDE","DAC_READ_SEARCH","FOWNER"]
    tmpfs={"/tmp":"rw,noexec,nosuid,nodev,size=256m,mode=1777"}
    env=[
        f"ENERGIE_PREPARED_JOB_REQUEST_ID={request_id}",
        f"ENERGIE_PREPARED_JOB_OPERATION={operation}",
        f"ENERGIE_PREPARED_JOB_RUNNER_SHA256={request['runner_sha256']}",
        f"ENERGIE_PREPARED_JOB_MANIFEST_SHA256={request['manifest_sha256']}",
        f"ENERGIE_PREPARED_JOB_PREDECESSOR_SHA256={request['predecessor_sha256']}",
        f"ENERGIE_PREPARED_JOB_TASK_ID={request['task_id']}",
        f"ENERGIE_PREPARED_JOB_TARGET_RELEASE={request['target_release']}",
        f"ENERGIE_PREPARED_JOB_PREDECESSOR_RELEASE={request['predecessor_release']}",
        "PYTHONDONTWRITEBYTECODE=1","PYTHONUNBUFFERED=1",
    ]
    if operation in {"TEST","BUILD"}:
        caps.extend(["SETUID","SETGID"])
        tmpfs={
            "/tmp":"rw,exec,nosuid,nodev,size=512m,mode=1777",
            "/config":"rw,nosuid,nodev,size=64m,mode=1777",
            "/share":"rw,nosuid,nodev,size=256m,mode=1777",
        }
        env.append("PYTEST_DISABLE_PLUGIN_AUTOLOAD=1")
    return {
        "Image":str(image_id).lower(),"Cmd":["python3","-c",BOOTSTRAP],
        "WorkingDir":"/job","Env":env,"Tty":True,
        "Labels":{
            "com.energie.component":"prepared-job","com.energie.request_id":request_id,
            "com.energie.operation":operation,"com.energie.runner_sha256":request["runner_sha256"],
            "com.energie.authorization_sha256":request["authorization_sha256"],
        },
        "HostConfig":{
            "Binds":[f"{host_root}:/project:ro",f"{job_host}:/job:rw"],
            "NetworkMode":"none","ReadonlyRootfs":True,"CapDrop":["ALL"],"CapAdd":caps,
            "SecurityOpt":["no-new-privileges"],"Tmpfs":tmpfs,"Init":True,
            "PidsLimit":512,"Memory":2147483648,"AutoRemove":False,
        },
    }

def _receipt(logs: str) -> dict:
    for line in reversed((logs or "").splitlines()):
        if line.startswith(RECEIPT_PREFIX):
            value=json.loads(line[len(RECEIPT_PREFIX):])
            return value if isinstance(value,dict) else {}
    return {}

def _terminal_result(path: Path, request: dict) -> bool:
    try:value=_json(path)
    except Exception:return False
    return bool(
        value.get("schema")==RESULT_SCHEMA and value.get("action")==ACTION
        and value.get("request_id")==request.get("request_id")
        and value.get("authorization_sha256")==request.get("authorization_sha256")
        and value.get("status") in {"GREEN","RED"}
    )

def _discover_host_root(control_plane) -> str:
    info=control_plane.docker.inspect_container(CONTROL_PLANE_CONTAINER)
    if not isinstance(info,dict):
        raise RuntimeError("control-plane container missing for host-root discovery")
    for mount in info.get("Mounts") or []:
        if isinstance(mount,dict) and mount.get("Destination")=="/control-plane":
            source=str(mount.get("Source") or "").rstrip("/")
            if not source.endswith(CONTROL_PLANE_SUFFIX):
                raise RuntimeError("control-plane source mount suffix mismatch")
            return source[:-len(CONTROL_PLANE_SUFFIX)]
    raise RuntimeError("control-plane source mount unavailable")

def _execute(control_plane, request: dict) -> dict:
    _claim_authorization(control_plane,request)
    request_id=request["request_id"]
    result_path=control_plane.result_root/"results"/f"prepared_job_run.{request_id}.json"
    if _terminal_result(result_path,request):
        return _json(result_path)
    container=f"energie-prepared-job-{request_id[:12]}"
    control_plane.docker.ping()
    image=control_plane.docker.inspect_image(IMAGE)
    image_id=str(image.get("Id") or "").lower() if isinstance(image,dict) else ""
    payload=_payload(_discover_host_root(control_plane),request,image_id)
    existing=control_plane.docker.inspect_container(container)
    if existing is not None:
        labels=existing.get("Config",{}).get("Labels",{}) if isinstance(existing,dict) else {}
        for key,expected in {
            "com.energie.request_id":request_id,
            "com.energie.runner_sha256":request["runner_sha256"],
            "com.energie.operation":request["operation"],
            "com.energie.authorization_sha256":request["authorization_sha256"],
        }.items():
            if labels.get(key)!=expected:
                raise RuntimeError("existing prepared job container identity mismatch")
    created=existing is not None; logs=""; exit_code=None; error=None; cleanup=False
    try:
        if existing is None:
            control_plane.docker.create_container(container,payload); created=True
            control_plane.docker.start_container(container)
        deadline=time.monotonic()+OPERATIONS[request["operation"]]
        while time.monotonic()<deadline:
            control_plane._write_runtime_marker()
            info=control_plane.docker.inspect_container(container)
            if not isinstance(info,dict):
                raise RuntimeError("prepared job container disappeared")
            state=info.get("State") if isinstance(info.get("State"),dict) else {}
            if state.get("Running") is not True:
                exit_code=int(state.get("ExitCode") if state.get("ExitCode") is not None else -1); break
            time.sleep(1.0)
        else:error="prepared job timeout"
        try:logs=control_plane.docker.container_logs(container)
        except Exception as exc:
            if error is None:error=f"logs readback failed:{type(exc).__name__}:{exc}"
    except Exception as exc:error=f"{type(exc).__name__}:{exc}"
    finally:
        if created:
            try:control_plane.docker.remove_container(container,force=True); cleanup=True
            except Exception as exc:
                if error is None:error=f"cleanup failed:{type(exc).__name__}:{exc}"
    receipt=_receipt(logs)
    receipt_ok=bool(
        receipt.get("status")=="GREEN" and receipt.get("request_id")==request_id
        and receipt.get("operation")==request["operation"]
        and receipt.get("runner_sha256")==request["runner_sha256"]
        and receipt.get("manifest_sha256")==request["manifest_sha256"]
        and receipt.get("predecessor_sha256")==request["predecessor_sha256"]
        and receipt.get("project_mount")=="read_only" and receipt.get("job_mount")=="read_write"
        and receipt.get("network_mode")=="none" and receipt.get("docker_socket_mounted") is False
    )
    ok=exit_code==0 and error is None and cleanup and receipt_ok
    result={
        "schema":RESULT_SCHEMA,"action":ACTION,"request_id":request_id,
        "task_id":request["task_id"],"operation":request["operation"],
        "target_release":request["target_release"],"predecessor_release":request["predecessor_release"],
        "predecessor_sha256":request["predecessor_sha256"],"runner_sha256":request["runner_sha256"],
        "manifest_sha256":request["manifest_sha256"],"authorization_sha256":request["authorization_sha256"],
        "image":IMAGE,"image_id":image_id,"container":container,"exit_code":exit_code,
        "network_mode":"none","project_mount":"read_only","job_mount":"read_write",
        "docker_socket_mounted":False,"production_modified":False,"container_removed":cleanup,
        "container_receipt":receipt,"logs_sha256":hashlib.sha256(logs.encode("utf-8",errors="replace")).hexdigest(),
        "status":"GREEN" if ok else "RED","ok":ok,
        "error":error if error is not None else (None if receipt_ok else "prepared job receipt missing/invalid"),
        "finished_at":datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(result_path,result)
    return result

def process_pending(control_plane, *, max_items: int=1) -> list[dict]:
    request_dir=control_plane.result_root/"requests"
    if request_dir.is_symlink() or not request_dir.is_dir():
        return []
    out=[]
    for path in sorted(request_dir.glob("prepared_job_run.*.json")):
        if len(out)>=max(1,int(max_items)):break
        request_id=path.name.removeprefix("prepared_job_run.").removesuffix(".json")
        if not REQUEST_ID_RE.fullmatch(request_id):continue
        try:
            request=_load_request(path)
            if request["request_id"]!=request_id:
                raise RuntimeError("request filename identity mismatch")
            result_path=control_plane.result_root/"results"/f"prepared_job_run.{request_id}.json"
            if _terminal_result(result_path,request):
                continue
            out.append(_execute(control_plane,request))
        except Exception as exc:
            probe={}
            try:probe=_load_request(path)
            except Exception:pass
            result_path=control_plane.result_root/"results"/f"prepared_job_run.{request_id}.json"
            result={
                "schema":RESULT_SCHEMA,"action":ACTION,"request_id":request_id,
                "authorization_sha256":str(probe.get("authorization_sha256") or ""),
                "production_modified":False,"status":"RED","ok":False,
                "error":f"{type(exc).__name__}:{exc}","finished_at":datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(result_path,result); out.append(result)
    return out
