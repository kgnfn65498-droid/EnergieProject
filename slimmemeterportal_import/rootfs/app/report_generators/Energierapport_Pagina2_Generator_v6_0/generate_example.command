#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 src/generate_p2.py --data data/juli_2026.json --output output/Energierapport_Pagina2_voorbeeld.pdf
open output/Energierapport_Pagina2_voorbeeld.pdf 2>/dev/null || true
