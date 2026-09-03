# Changelog

## 32.3.24

- CLOSED-rerender gebruikt een verse historische validatie uit de actuele maand-readiness.
- Oude `central_validation.json`-resultaten van een eerdere workflow worden niet als actuele rerender-validatie hergebruikt.
- De historische eindcontrole gebruikt de validatie uit de actuele report-handoff, niet een oude globale workflowstatus.
- Reguliere maandworkflowvalidatie blijft ongewijzigd.
- v32.3.23 bronbescherming en Analysis-onafhankelijkheid blijven behouden.
