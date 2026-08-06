# Bouwinstructie vanaf een lege computer

## Vereisten
- Python 3.11 of hoger
- Geen extern lettertype nodig; de standaard PDF-fonts worden gebruikt

## Installatie
```bash
cd Energierapport_Pagina1_Echte_Generator_v6
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Voorbeeld bouwen
```bash
python build_example.py
```
Uitvoer: `output/Energierapport_pagina1_voorbeeld_v6.pdf`.

## Nieuwe maand bouwen
```bash
cp maanddata_voorbeeld.json maanddata_2026_08.json
# Pas uitsluitend de waarden in de kopie aan.
python verwerk_maandupdate.py maanddata_2026_08.json -o output/Energierapport_pagina1_2026_08.pdf
```

## Validatie en tests
```bash
python -m pip install -r requirements-dev.txt
python validate_maanddata.py maanddata_2026_08.json
pytest -q
python controleer_pakket.py
```

## Visuele PDF-controle
```bash
python /home/oai/skills/pdfs/scripts/render_pdf.py output/Energierapport_pagina1_voorbeeld_v6.pdf --out_dir output/render --dpi 200
```
Op systemen zonder die controlescripts kan de PDF normaal in Voorvertoning of Acrobat worden gecontroleerd.
