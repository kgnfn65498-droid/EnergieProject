# Testinstructies v12.2.0

1. Plaats `EnergieProject_v12.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar EnergieProject 12.2.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v12_decision_support`.
7. Huidige verwachte toestand: `recommendation_publishable=false`, `recommendation_strength=null`, `safety_margin_pct=5.0`.
8. De 7-dagen- en contractgates blijven verplicht.
9. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29 en is geen leverancier-all-in prijs.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
