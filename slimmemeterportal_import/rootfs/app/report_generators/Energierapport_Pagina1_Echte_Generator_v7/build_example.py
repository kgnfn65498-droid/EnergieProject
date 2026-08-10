#!/usr/bin/env python3
from pathlib import Path
from generate_energierapport_pagina1 import generate

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "Energierapport_pagina1_voorbeeld_v6.pdf"

def main() -> None:
    generate(ROOT / "maanddata_voorbeeld.json", OUT, ROOT / "assets")
    print(OUT)

if __name__ == "__main__": main()
