# Energierapport pagina 1 - reproduceerbare Python-generator v7

Dit pakket bevat alles wat nodig is om pagina 1 opnieuw te genereren met nieuwe maanddata. De volledige pagina wordt door ReportLab opgebouwd uit vectorobjecten; alleen `assets/woning.png` is een fotoasset. Er wordt geen bestaande PDF-pagina als achtergrond gekopieerd.

## Snel starten

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python verwerk_maandupdate.py maanddata_voorbeeld.json -o output/nieuwe_maand.pdf
```

## Vaste template

De geometrie, kleuren, fonts, blokposities en grafiekposities staan uitsluitend in `generate_energierapport_pagina1.py`. Nieuwe maanddata worden vooraf gevalideerd. Aantallen KPI's en grafiekpunten zijn vastgelegd zodat gewijzigde data de pagina-indeling niet verschuiven.

## Belangrijkste bestanden

- `generate_energierapport_pagina1.py`: volledige teken- en layoutcode.
- `verwerk_maandupdate.py`: productie-ingang voor een maandupdate.
- `validate_maanddata.py`: inhouds- en layoutcontractvalidatie.
- `maanddata_voorbeeld.json`: invulbaar voorbeeld.
- `maanddata_schema.json`: machineleesbare datastructuur.
- `assets/woning.png`: enige vereiste beeldasset.
- `build_example.py`: bouwt de meegeleverde voorbeeld-PDF.
- `tests/`: regressie- en reproduceerbaarheidstests.
- `controleer_pakket.py`: controleert compleetheid en maakt SHA-256-manifest.

Zie `BOUWINSTRUCTIE.md` en `MAANDUPDATE_WERKWIJZE.md` voor de volledige procedure.

## Managementsamenvatting

De generator sorteert de punten automatisch op statuskleur: **groen, oranje, rood**. Binnen dezelfde kleur blijft de JSON-volgorde behouden.
