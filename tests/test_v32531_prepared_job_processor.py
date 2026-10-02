import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PM=ROOT/"slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0,str(PM))

from prepared_job_command_processor import PreparedJobCommandProcessor


class FakeCommands:
    def __init__(self,item):
        self.item=dict(item)
    def all(self):
        return [dict(self.item)]
    def claim_next(self):
        if self.item.get("status") not in {"PENDING","APPROVED_READY"}:
            return None
        self.item["status"]="PROCESSING"
        return dict(self.item)
    def requeue(self,item_id,*,result):
        assert item_id==self.item["id"]
        self.item.update(status="PENDING",pending_reason="external_executor_pending",result=result)
        return dict(self.item)
    def complete(self,item_id,*,result):
        assert item_id==self.item["id"]
        self.item.update(status="DONE",result=result)
        return dict(self.item)
    def fail(self,item_id,*,error):
        assert item_id==self.item["id"]
        self.item.update(status="FAILED",error=error)
        return dict(self.item)


class FakeTasks:
    def active(self):
        return {"id":"task-1","mode":"DEVELOPMENT","status":"ACTIVE"}


class FakeService:
    def __init__(self,result):
        self.result=dict(result)
        self.calls=[]
    def run(self,**kwargs):
        self.calls.append(kwargs)
        return dict(self.result)


def _processor(service):
    item={
        "id":"cmd-1","status":"PENDING","intent":"prepared_job_run",
        "artifact_path":"Data/03_Systeem/Projectmanager/Staging/PreparedJobs/32531a04c0ffee001122334455667788/runner.py",
        "artifact_sha256":"a"*64,
        "release_version":"32.5.31",
        "classification_hint":"TEST",
    }
    commands=FakeCommands(item)
    processor=PreparedJobCommandProcessor(
        commands,None,None,FakeTasks(),
        prepared_job_service=service,
        project_root=None,
    )
    processor._guard_active_transition_mutation=lambda *a,**k: None
    processor._guard_transition_ticket=lambda *a,**k: None
    processor._guard_release_owned_closure=lambda *a,**k: None
    return processor,commands


def test_prepared_job_pending_is_requeued_without_user_terminal():
    service=FakeService({"status":"PENDING","ok":None,"awaiting_executor":True})
    processor,commands=_processor(service)
    result=processor.process_next()
    assert result["status"]=="PENDING"
    assert result["pending_reason"]=="external_executor_pending"
    assert service.calls==[{
        "task":{"id":"task-1","mode":"DEVELOPMENT","status":"ACTIVE"},
        "artifact_path":commands.item["artifact_path"],
        "artifact_sha256":"a"*64,
        "target_release":"32.5.31",
        "operation":"TEST",
    }]


def test_prepared_job_green_requires_bounded_executor_receipt():
    service=FakeService({
        "status":"GREEN","ok":True,"network_mode":"none",
        "project_mount":"read_only","production_modified":False,
        "container_removed":True,
    })
    processor,_=_processor(service)
    result=processor.process_next()
    assert result["status"]=="DONE"
    assert result["result"]["executed"] is True
    assert result["result"]["action"]=="prepared_job_run"


def test_prepared_job_unbounded_result_fails_closed():
    service=FakeService({
        "status":"GREEN","ok":True,"network_mode":"bridge",
        "project_mount":"read_write","production_modified":False,
        "container_removed":True,
    })
    processor,_=_processor(service)
    result=processor.process_next()
    assert result["status"]=="FAILED"
    assert "geen GREEN bounded resultaat" in result["error"]
