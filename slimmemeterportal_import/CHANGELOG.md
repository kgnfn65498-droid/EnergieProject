# Changelog

## 32.4.51

- Projectmanager singleton-lock conflict stopt de worker niet meer permanent; bounded retry en periodieke lifecycle-supervisie houden PM- en release-hold-workers actief.
- Project-CR en NAS Container CR zijn voor de Projectmanager non-blocking; zware Project-CR draait detached van de watcher-hoofdloop.
- Projectmanager driver-liveness is een expliciete release-health gate; stale GREEN self-audit maskeert geen stilgevallen closure meer.
- Nieuwe-chat handover bevat audit-recurrencecontract, ontwikkelmethode, requirement-preflight en de ChatGPT-bouw/Codex-onderzoek-rolverdeling.
- `release_recover` gebruikt uitsluitend de bestaande canonieke release- en protected-actionroutes en vraagt alleen watcher-recreate-goedkeuring wanneer die echt nodig is.
- Target identity: EnergieProject 32.4.51 / Projectmanager 2.0.0-rc38.
