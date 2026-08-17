# Changelog

## 32.3.10 - Nomad automation auto-registration hotfix
- Registreert `Nomad - Energie Assistent` automatisch via de bestaande Home Assistant Core configuration API.
- Payload bevat geen handmatig `id`; Home Assistant beheert de automation-ID.
- Idempotent en fail-closed: bestaande eigen automation blijft staan; een conflict wordt nooit overschreven.
- Geen extra rechten: alleen `homeassistant_api: true`; geen HACS/custom component/Terminal/device-control/`finalize_month`.
