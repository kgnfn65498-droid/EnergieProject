import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _path(value) -> Path:
    return value if isinstance(value, Path) else Path(value)


def atomic_write_text(path, content: str) -> None:
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    atomic_write_text(path, text)


def load_json(path, default=None):
    target = _path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding='utf-8'))


def append_jsonl(path, payload: Any) -> None:
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + '\n'
    with target.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
