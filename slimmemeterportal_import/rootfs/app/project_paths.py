from __future__ import annotations

from pathlib import Path

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

def resolve_nas_roots(share_root: Path = Path("/share")) -> tuple[Path, Path]:
    # Resolveer de actuele HA netwerkshare zonder afhankelijkheid van één opslagnaam.
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

    # Fail-closed fallback: geen willekeurige andere share kiezen.
    preferred = share_root / "Project Energie"
    return preferred, preferred
