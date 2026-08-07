# Changelog v8.17.0

- Recoveryfase uit de roadmap toegevoegd zonder refactor van de bestaande maandworkflow.
- Nieuwe Recovery v8.17-controller voert bij add-onstart automatisch een conservatieve statuscontrole uit.
- Herstelt uitsluitend status die uit bestaand hard bewijs kan worden afgeleid:
  - achtergebleven persistente workflow-lockstatus na een procesherstart;
  - automatische retry-state via append-only runhistorie, workflow_result of completion-marker;
  - productiecertificaat uitsluitend uit een aantoonbaar geslaagde productietest van exact v8.17.0.
- Recovery start nooit zelfstandig een maandworkflow.
- Een ongeldige auditketen wordt nooit automatisch aangepast; die blijft een handmatig aandachtspunt.
- Recovery-resultaat wordt opgeslagen in `/config/output/recovery_state.json`.
- Append-only recoveryhistorie wordt opgeslagen in `/config/output/recovery_history.jsonl`.
- Recovery-acties worden, zolang de auditketen geldig is, ook vastgelegd in de bestaande audittrail.
- Nieuwe consolekaart **Recovery v8.17** met status, aantal herstelacties, tijdstip en één knop voor handmatige hercontrole.
- De resterende v8.16.1 UI-fout is meegenomen: **Controleer / herstel productiecertificaat** werkt nu via fetch in dezelfde Home Assistant-ingresspagina en navigeert niet meer naar een zwarte/lege pagina.
- Audittrail, scheduler, retry, rapportgeneratoren, outputcontract en maandworkflow blijven backwards compatible.
