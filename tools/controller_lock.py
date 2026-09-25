from __future__ import annotations
from system_path_contract import project_system_path
import contextlib,fcntl,os,stat
from pathlib import Path

@contextlib.contextmanager
def controller_lease(root:Path):
    path=project_system_path(Path(root), 'Inbox/.release-controller.lock')
    path.parent.mkdir(parents=True,exist_ok=True)
    flags=os.O_RDWR|os.O_CREAT
    if hasattr(os,'O_NOFOLLOW'):flags|=os.O_NOFOLLOW
    fd=os.open(str(path),flags,0o644)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):raise RuntimeError('controller lock unsafe')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise RuntimeError('release controller already active') from exc
        yield
    finally:
        try:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)
