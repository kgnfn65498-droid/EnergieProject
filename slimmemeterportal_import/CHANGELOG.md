# Changelog

## 32.0.33 - Juli ingress/fallback
- De vaste `Data/01_Input/YYYY_MM/HomeAssistant`-ingress wordt veilig en idempotent aangemaakt als die nog ontbreekt.
- SlimmeMeterPortal-publicatie blijft daardoor mogelijk voor een afgesloten maand waarin lokale P1/HomeWizard-historie pas later in de maand beschikbaar kwam.
- De bestaande `HomeAssistant/SlimmeMeterPortal`-layout, staging/checksum/swap-logica en duurzame completion-marker blijven ongewijzigd.
- Een onbruikbare of onbeschrijfbare NAS-ingress blijft een harde fout.
- Geen wijziging aan Crash Recovery, watcher-cleanup, GitHub-publicatie, augustus 2026 of `finalize_month`.
