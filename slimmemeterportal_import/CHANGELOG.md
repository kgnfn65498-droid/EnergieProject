# Changelog

## 7.0.1
- Nieuwe operationele console boven de bestaande fase-7 workflow.
- Statuskaarten voor workflow, laatste maand, laatste run en automatische maandafsluiting.
- Live voortgangsweergave via bestaande status-endpoints, zonder nieuwe workflowlogica.
- Historische workflowresultaten als tabel met status, stappen, duur en mislukte stap.
- Bediening logisch gegroepeerd; technische functies blijven beschikbaar onder diagnostiek/beheer.
- Bestaande rapportketen, Recovery Update-contract en outputnamen ongewijzigd.

## 7.0.0
- Fase-7 besturingslaag toegevoegd boven de bestaande maandworkflow.
- Optionele automatische maandafsluiting op instelbare dag en uur.
- Historische maandselectie via de Ingress-interface, zonder live snapshots aan oude maanden toe te voegen.
- Compact endpoint `operation-status` met actuele workflowstatus en recente maandhistorie.
- Bestaande rapportketen, bestandsnamen en Recovery Update-inhoud blijven ongewijzigd.

## 6.9.1
- Stabiele afsluiting van fase 6.
