# Testinstructies v14.3.0

1. Plaats `EnergieProject_v14.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Open vóór installatie het Home Assistant-updatevenster.
4. Controleer dat daar alleen release **14.3.0** staat en geen oude releaseblokken meer zichtbaar zijn.
5. Update Home Assistant naar 14.3.0.
6. Controleer GUI/Ingress.
7. Download Analyse-export en release-diagnose.
8. Controleer `production_consolidation.v14_completion_gate`.
9. Verwacht `release_status = v14_complete_external_data_gates_remain`.
10. Zolang minder dan 7 dagen beschikbaar zijn, blijven prognosevelden geblokkeerd.
11. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
12. EPEX blijft uitsluitend referentie.
13. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
