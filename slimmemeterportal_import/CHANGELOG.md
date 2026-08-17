# Changelog

## 32.3.9 - Nomad native Home Assistant event bridge
- Native Home Assistant Sentence/event-bridge voor Nomad zonder HACS of custom component.
- `energie_nomad_request` -> bestaande read-only assistantbackend -> `energie_nomad_response`; privacy via automation aan/uit.
- Configureerbare displaynaam en begroeting; standaard `Nomad`, begroeting opnieuw na 900 seconden stilte.
- `hassio_api`, `hassio_role` en Supervisor discovery verwijderd; alleen `homeassistant_api: true` blijft.
- Geen device-control, contractmutatie, projectwrite, externe poortmapping, maandafsluiting of `finalize_month`.
