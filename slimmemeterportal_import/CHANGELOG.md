# Changelog

## 32.3.2 - Assistant runtime observability
- Fixed-target read-only self-probe valideert na add-on-start de echte assistant HTTP-routes via `127.0.0.1:8099`.
- Runtimeacceptatie controleert health/version, augustus PARTIAL + kwartierbron, sessie-follow-up naar juli, NextEnergy zonder factuuractual en Knowledge Base-provenance voor apparatuur.
- Extra assistant payloadvelden worden fail-closed geweigerd; requestlimiet 32 KiB, probe-responslimiet 256 KiB en timeout 5 seconden.
- Acceptance-resultaat wordt naar de bestaande Projectmanager-state op de NAS geschreven; Voice blijft gesloten bij iedere fout en wordt niet automatisch geactiveerd.
- Geen energieactuals, automatische maandafsluiting, `finalize_month`, MCP-rechten of system-pad guard gewijzigd.
