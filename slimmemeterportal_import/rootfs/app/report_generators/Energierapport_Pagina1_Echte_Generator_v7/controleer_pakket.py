#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "generate_energierapport_pagina1.py", "verwerk_maandupdate.py", "validate_maanddata.py",
    "build_example.py", "maanddata_voorbeeld.json", "maanddata_schema.json",
    "assets/woning.png", "requirements.txt", "requirements-dev.txt", "README.md",
    "BOUWINSTRUCTIE.md", "MAANDUPDATE_WERKWIJZE.md", "tests/test_generator.py"
]

def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    if missing:
        print("ONTBREEKT:")
        print("\n".join(missing))
        return 1
    manifest = ROOT / "MANIFEST_SHA256.txt"
    lines=[]
    for path in sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name != manifest.name and '__pycache__' not in p.parts):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    manifest.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Pakket compleet: {len(lines)} bestanden; manifest bijgewerkt")
    return 0

if __name__ == "__main__": raise SystemExit(main())
