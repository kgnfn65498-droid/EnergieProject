## 32.0.8 - Server-rendered GitHub-publicatiestatus
- GitHub-publicatiestatus wordt server-side uit de persistente publisher-state opgebouwd.
- De browser gebruikt voor deze kaart geen netwerkfetch meer.
- Legacy observability-hooks blijven als no-op compatibiliteitslaag aanwezig.
- Publisher-thread, GitHub-publicatie, energie-, rapport- en recoverylogica blijven ongewijzigd.

# Changelog

## 32.0.8
- Onderhoudsfix voor Home Assistant Ingress/Safari `TypeError: Load failed`.
- Geen functionele wijziging buiten de HA-publicatiestatuskaart.
