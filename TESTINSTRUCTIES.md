# Testinstructies v19.2.0

1. Plaats de ZIP in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v19_report_action_quality_context.status = report_action_quality_context_active`.
5. Bij circa 4,562/7 dagen (65,2%) blijft het advies geblokkeerd wegens onvoldoende meetdekking.
6. Meetvoortgang en resterende waarnemingsdagen moeten beschikbaar zijn.
7. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
8. Candidate-getallen zijn geen primaire rapportwaarden; ontbrekende waarden blijven `Niet beschikbaar`.
9. EPEX blijft uitsluitend markt-/referentieprijs.

10. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
