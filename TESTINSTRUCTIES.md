# Testinstructies v14.1.0

1. Plaats `EnergieProject_v14.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 14.1.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v14_report_value_mapping.status = mapped_guarded`.
7. Controleer dat `zero_fallback_allowed = false`.
8. Zolang minder dan 7 dagen zijn waargenomen, blijven prognosewaarden niet-publiceerbaar.
9. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
