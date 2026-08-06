#!/bin/bash
cd "$(dirname "$0")"
python3 src/generate_pages_3_13.py
open output/Energierapport_Pagina3_tm_13_voorbeeld_v1.pdf
