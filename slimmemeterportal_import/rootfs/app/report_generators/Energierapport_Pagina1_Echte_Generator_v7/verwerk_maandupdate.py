#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from generate_energierapport_pagina1 import generate
from validate_maanddata import load_and_validate, DataValidationError

def main() -> int:
    p = argparse.ArgumentParser(description="Valideer maanddata en genereer pagina 1 met vaste template-layout.")
    p.add_argument("maanddata", help="JSON-bestand met nieuwe maandwaarden")
    p.add_argument("-o", "--output", default="output/Energierapport_pagina1_maandupdate.pdf")
    args = p.parse_args()
    root = Path(__file__).resolve().parent
    src = Path(args.maanddata).expanduser().resolve()
    out = Path(args.output).expanduser()
    if not out.is_absolute(): out = root / out
    try:
        load_and_validate(src)
        generate(src, out, root / "assets")
    except DataValidationError as exc:
        p.error(str(exc))
    print(out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
