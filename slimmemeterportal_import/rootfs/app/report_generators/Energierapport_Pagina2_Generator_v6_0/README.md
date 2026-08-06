# Energierapport Pagina 2 Generator v6.0

Een zelfstandige Python/ReportLab-generator voor pagina 2 van het energierapport.
De pagina wordt volledig programmatisch opgebouwd. De referentie-PDF wordt niet als achtergrond of overlay gebruikt.

## Genereren

```bash
python3 src/generate_p2.py \
  --data data/juli_2026.json \
  --output output/Energierapport_Pagina2_voorbeeld_v6.pdf
```

## Testen

```bash
python3 -m unittest discover -s tests
```

De maandwaarden staan in `data/juli_2026.json`. De layout staat vast in `src/generate_p2.py`.


## Wijziging v6.0
De kostentrendgrafiek in sectie 3 bevat een zichtbare x-as met maandlabels juli tot en met juni.
