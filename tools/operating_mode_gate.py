#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _app_module_root(project_root: Path) -> Path:
    candidates = (
        project_root / "App/slimmemeterportal_import/rootfs/app",
        project_root / "slimmemeterportal_import/rootfs/app",
        Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app",
    )
    for candidate in candidates:
        if (candidate / "operating_modes.py").is_file():
            return candidate
    raise RuntimeError("canonical operating_modes.py not found")


def _load_api(project_root: Path):
    app_root = _app_module_root(project_root)
    sys.path.insert(0, str(app_root))
    from operating_modes import load_mode_state, profile_for, state_path
    return load_mode_state, profile_for, state_path


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument(
        "--capability",
        required=True,
        choices=("release_ingress", "maintenance_requests", "status"),
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    try:
        load_mode_state, profile_for, state_path = _load_api(root)
        path = state_path(root)
        if not path.is_file():
            _print({"status": "error", "error": "operating_mode_state_missing"})
            return 4
        state = load_mode_state(root)
        if "legacy_or_invalid_state_migrated" in state.drift:
            _print({"status": "error", "error": "operating_mode_state_invalid"})
            return 4
        profile = profile_for(state.effective_mode, state.suspended_features)
    except Exception as exc:
        _print({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 4

    if args.capability == "status":
        _print({
            "status": "ok",
            "base_mode": state.base_mode.value,
            "effective_mode": state.effective_mode.value,
            "automatic_switching_enabled": state.automatic_switching_enabled,
            "reconciliation_status": state.reconciliation_status,
        })
        return 0

    allowed = (
        profile.release_ingress_enabled
        if args.capability == "release_ingress"
        else profile.maintenance_request_processing_enabled
    )
    _print({
        "status": "allowed" if allowed else "denied",
        "capability": args.capability,
        "effective_mode": state.effective_mode.value,
    })
    return 0 if allowed else 3


if __name__ == "__main__":
    raise SystemExit(main())
