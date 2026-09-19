from __future__ import annotations
import json, os, stat
from pathlib import Path

class StateStore:
    def __init__(self, path: Path):
        self.path=Path(path)

    def load(self) -> dict | None:
        try:
            st=self.path.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RuntimeError('release state path unsafe')
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError('release state unreadable') from exc
        if not isinstance(value,dict):
            raise RuntimeError('release state must be object')
        return value

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise RuntimeError('release state path unsafe')
        tmp=self.path.with_name('.'+self.path.name+f'.tmp-{os.getpid()}')
        try:
            with tmp.open('x',encoding='utf-8') as h:
                json.dump(state,h,ensure_ascii=False,sort_keys=True,indent=2)
                h.write('\n'); h.flush(); os.fsync(h.fileno())
            os.replace(tmp,self.path)
        finally:
            tmp.unlink(missing_ok=True)
