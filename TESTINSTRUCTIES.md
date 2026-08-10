# Testinstructies v20.4.0

1. Plaats `EnergieProject_v20.4.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_savings_opportunity_engine.status = savings_opportunity_engine_active_guarded`.
5. Controleer `roadmap_state = v20_reporting_baseline_complete_savings_development_continues`.
6. Controleer opportunity types: energy_contract, home_battery, appliance_replacement en load_shifting.
7. Marstek Venus 3 mag alleen als kandidaat staan; ontbrekende batterijgegevens mogen niet worden geschat.
8. Apparaatvervanging mag pas advies geven met complete meet- en vervangingsgegevens.
9. De bestaande 7-dagen prognosegate blijft werken.
10. Supplier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
11. EPEX blijft uitsluitend markt-/referentieprijs.
12. Historische EPEX juli 2026 blijft **gedeeltelijk**: brondata loopt t/m 2026-07-29.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
