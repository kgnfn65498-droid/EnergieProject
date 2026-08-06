# Maandupdate

1. Valideer eerst de verplichte bronnen: P1, Enphase, EPEX-elektriciteit, EPEX-gas en airco.
2. Noteer welke optionele HomeWizard-socketbestanden aanwezig of afwezig zijn; behandel ontbrekende mobiele of seizoensmetingen nooit als bewust ontbrekend zonder bevestiging.
3. Kopieer `maanddata_voorbeeld.json` naar een bestand met jaar en maand.
4. Wijzig alleen gegevenswaarden en teksten binnen de vastgelegde maximale lengtes.
5. Voer `python validate_maanddata.py <bestand.json>` uit.
6. Genereer met `python verwerk_maandupdate.py <bestand.json> -o <uitvoer.pdf>`.
7. Render en controleer op clipping, overlap en ontbrekende tekens.
8. Archiveer brondata, gebruikte JSON, PDF, generatorversie en SHA-256-manifest samen.

De validator blokkeert aantallen die de vaste layout zouden wijzigen, waaronder niet precies 7 bovenste KPI's, 6 onderste KPI's, 4 jaarwaarden, 12 maandwaarden, 5 scoreonderdelen en 6 batterijpunten.
