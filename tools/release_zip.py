#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import zipfile


def _safe_members(zf: zipfile.ZipFile):
    for info in zf.infolist():
        p = Path(info.filename)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"unsafe ZIP member: {info.filename}")
        yield info


def cmd_test(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as zf:
            list(_safe_members(zf))
            bad = zf.testzip()
            if bad:
                print(bad, file=sys.stderr)
                return 1
        return 0
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_list(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as zf:
            for info in _safe_members(zf):
                print(info.filename)
        return 0
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


def cmd_extract(path: Path, destination: Path) -> int:
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as zf:
            members = list(_safe_members(zf))
            zf.extractall(destination, members=members)
        return 0
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("test", "list", "extract"))
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()

    if args.command == "test":
        return cmd_test(args.zip_path)
    if args.command == "list":
        return cmd_list(args.zip_path)
    if args.destination is None:
        parser.error("extract vereist destination")
    return cmd_extract(args.zip_path, args.destination)


if __name__ == "__main__":
    raise SystemExit(main())
