# Testinstructies v15.2.0

1. Plaats `EnergieProject_v15.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 15.2.0 toont.
4. Update naar 15.2.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v15_report_render_safety.status = render_safety_active`.
7. Bij de huidige observatie van circa 4,1/7 dagen moeten prognosewaarden nog geblokkeerd blijven.
8. Leverancier-all-in en voorschotvergelijking blijven geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
9. Validatie-candidates mogen niet als financiële prognose worden gepubliceerd.
10. Ontbrekende financiële waarden blijven `Niet beschikbaar`; nooit 0.
11. EPEX blijft uitsluitend referentie.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
