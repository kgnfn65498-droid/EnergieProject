from __future__ import annotations

from pathlib import Path
import time
from typing import Callable

PREFERRED_PROJECT_SHARE_NAMES = (
    "Project Energie",
    "Project_Energie",
    "Energie_NAS",
)

def _layout_for_mount(mount: Path) -> Path | None:
    direct = mount
    nested = mount / "EnergieProject"
    for candidate in (direct, nested):
        if (candidate / "App" / "VERSIE.txt").is_file() and (candidate / "Inbox").is_dir():
            return candidate
    return None


def find_existing_nas_roots(share_root: Path = Path("/share")) -> tuple[Path, Path] | None:
    """Return only a NAS layout that exists now; never return a writable fallback."""
    for name in PREFERRED_PROJECT_SHARE_NAMES:
        mount = share_root / name
        layout = _layout_for_mount(mount)
        if layout is not None:
            return mount, layout

    matches: list[tuple[Path, Path]] = []
    if share_root.is_dir():
        try:
            candidates = sorted((p for p in share_root.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())
        except OSError:
            candidates = []
        for mount in candidates:
            layout = _layout_for_mount(mount)
            if layout is not None:
                matches.append((mount, layout))

    if len(matches) == 1:
        return matches[0]
    return None


def wait_for_existing_nas_roots(
    share_root: Path = Path("/share"),
    *,
    attempts: int = 60,
    delay_seconds: float = 5.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[Path, Path]:
    """Wait for the real HA-mounted NAS project; never create/use the fallback path."""
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        resolved = find_existing_nas_roots(share_root)
        if resolved is not None:
            return resolved
        if attempt + 1 < attempts:
            sleep_fn(delay_seconds)
    raise RuntimeError(
        f"EnergieProject NAS-share niet beschikbaar onder {share_root}; "
        "geen lokale fallback gebruikt."
    )


def resolve_nas_roots(share_root: Path = Path("/share")) -> tuple[Path, Path]:
    # Compatibility resolver used by the existing runtime. If the real share is
    # already present, return it. Otherwise preserve the historic fail-closed
    # fallback path; new write paths must use wait_for_existing_nas_roots().
    resolved = find_existing_nas_roots(share_root)
    if resolved is not None:
        return resolved
    preferred = share_root / "Project Energie"
    return preferred, preferred
