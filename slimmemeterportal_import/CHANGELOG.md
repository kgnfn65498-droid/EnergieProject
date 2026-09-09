# Changelog

## 32.4.22 — CLOSED-maand startup-idempotency

- RecoveryManager `MonthClosure_<YYYY_MM>=CLOSED` is nu een harde idempotency-bron voor automatische maandafsluiting.
- Een ontbrekende lokale completion-marker kan een reeds CLOSED maand daardoor niet opnieuw starten.
- Automatische maandafsluiting wacht bij app-start totdat startup recovery/reconciliation is teruggekeerd; bij recovery-exception blijft deze fail-closed geblokkeerd.
- Handmatige workflows, reguliere import/sampling en de groene 32.4.21 releaseketen zijn niet gewijzigd.
- Projectmanager V2 2.0.0-rc19.
