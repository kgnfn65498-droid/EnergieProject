# Testinstructies v20.5.0

1. Plaats `EnergieProject_v20.5.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_savings_priority_engine.status = savings_priority_engine_active_guarded`.
5. Controleer dat ranking_dimensions jaarlijkse besparing, terugverdientijd, datacompleetheid en uitvoeringsinspanning bevat.
6. Controleer dat onvolledige kansen niet in de financiële ranking worden opgenomen.
7. Controleer dat ontbrekende waarden `Niet beschikbaar` blijven en niet als 0 worden ingevuld.
8. Controleer dat Marstek Venus 3 kandidaat blijft en niet vooraf als winnaar wordt geselecteerd.
9. Controleer dat apparaatvervanging pas rankt met gemeten jaarkosten, vervangingskosten/verbruik, jaarlijkse besparing en terugverdientijd.
10. De 7-dagen prognosegate blijft ongewijzigd werken.
11. Supplier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
12. EPEX blijft uitsluitend markt-/referentieprijs.
13. Historische EPEX juli 2026 blijft **gedeeltelijk**: brondata loopt t/m 2026-07-29.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
