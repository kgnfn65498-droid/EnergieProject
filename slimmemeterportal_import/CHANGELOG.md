# Changelog

## 32.3.19

- RELEASE VALIDATION HOLD wordt na een gezonde installatie automatisch via de normale vijf checks + reconciliation vrijgegeven.
- Crash Recovery backup/verify pauzeert automatische maand/workflowmutaties tijdens de tijdelijke MAINTENANCE-sessie.
- Post-download cleanup houdt MAINTENANCE vast totdat watcher-cleanup volledig is teruggekoppeld; onveilige cleanupfouten blijven MAINTENANCE.
- USER/DEVELOPMENT-basis en DEVELOPMENT-sessie blijven exact behouden.
