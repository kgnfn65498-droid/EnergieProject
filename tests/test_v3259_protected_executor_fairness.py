from pathlib import Path
import sys

PM = Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))
from protected_action_executor import ProtectedActionExecutor


class Actions:
    def __init__(self):
        self.items = [
            {"id": f"a{i}", "action": "native_mcp_reload", "command_id": f"c{i}", "decision_id": f"d{i}"}
            for i in range(6)
        ]
    def open_items(self):
        return list(self.items)
    def complete(self, *a, **k):
        pass


class Store:
    def get(self, key):
        return {"id": key}
    def complete(self, *a, **k):
        pass


def test_stale_first_five_do_not_starve_sixth_valid_action(tmp_path):
    ex = ProtectedActionExecutor(tmp_path, Actions(), Store(), Store())
    ex._validate_transition_command = lambda command, action: None
    seen = []
    def fake_queue(action, command, decision):
        seen.append(action["id"])
        if action["id"] != "a5":
            raise RuntimeError("stale historical approval")
        return {"ok": True, "awaiting_executor": True, "request_id": "r"}
    ex._queue_native_mcp_reload = fake_queue
    result = ex.run_once(max_items=5)
    assert seen == ["a0", "a1", "a2", "a3", "a4", "a5"]
    assert any(item.get("request_id") == "r" for item in result)
