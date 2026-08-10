# Testinstructies v21.1.0

1. Plaats `EnergieProject_v21.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_runtime_gate_resolution.status = runtime_gate_resolution_active_guarded`.
5. De gatevolgorde moet zijn: observation → supplier contract → opportunity inputs → actionable.
6. Met minder dan 7 waarnemingsdagen moet de financiële runtime geblokkeerd blijven op observation.
7. Na 7 dagen mag supplier-all-in nog steeds niet vrijgegeven worden zolang officiële NextEnergy-contractcomponenten ontbreken.
8. Ontbrekende bedragen blijven `Niet beschikbaar`/null en worden nooit €0.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Historische EPEX juli 2026 blijft **gedeeltelijk**: brondata loopt t/m 2026-07-29.
11. Bestaande v20 savings-keten en v21.0 runtime moeten intact blijven.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
