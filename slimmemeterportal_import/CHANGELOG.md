# Changelog

## 32.3.11 - Nomad automation reload hotfix
- Roept na installatie of detectie van de eigen Nomad-automation expliciet `automation.reload` aan via Home Assistant Core REST.
- Lost op dat de config-API `already_present` meldde terwijl Home Assistant nog geen `automation.nomad_energie_assistent` entity had geladen.
- Conflicterende automation-ID blijft fail-closed en wordt niet overschreven of door Nomad herladen.
- Geen extra rechten: alleen `homeassistant_api: true`; geen HACS/custom component/Terminal/device-control/`finalize_month`.
