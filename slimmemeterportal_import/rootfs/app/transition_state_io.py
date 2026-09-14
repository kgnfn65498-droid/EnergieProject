from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any


class TransitionStateReadError(RuntimeError):
    pass


def read_transition_state(path: Path | str, *, missing_ok: bool = True) -> dict[str, Any] | None:
    """Read transition state without following a symlink or non-regular final path.

    The lstat/open/fstat identity check also closes the replace-between-check-and-open
    window for the final path component. Invalid JSON is fail-closed because release
    transition truth must never silently degrade into "no active transition".
    """
    p = Path(path)
    try:
        before = p.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise TransitionStateReadError(f'transition state missing: {p}')
    except OSError as exc:
        raise TransitionStateReadError(f'transition state lstat failed: {p}') from exc

    if stat.S_ISLNK(before.st_mode):
        raise TransitionStateReadError(f'transition state path is symlink: {p}')
    if not stat.S_ISREG(before.st_mode):
        raise TransitionStateReadError(f'transition state path is not regular file: {p}')

    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(p), flags)
    except OSError as exc:
        raise TransitionStateReadError(f'transition state secure open failed: {p}') from exc
    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode):
            raise TransitionStateReadError(f'transition state opened object is not regular: {p}')
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise TransitionStateReadError(f'transition state changed during secure open: {p}')
        with os.fdopen(fd, 'r', encoding='utf-8') as handle:
            fd = -1
            try:
                value = json.load(handle)
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise TransitionStateReadError(f'transition state invalid JSON: {p}') from exc
    finally:
        if fd >= 0:
            os.close(fd)

    if not isinstance(value, dict):
        raise TransitionStateReadError(f'transition state is not an object: {p}')
    return value
