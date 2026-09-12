# Testinstructies v32.4.46 — control-plane archive + chatapproval closure

Minimale acceptatie vóór ZIP-uitgifte:

1. 32.4.46 control-plane archive- en chatapproval-regressies eerst RED gezien en daarna GREEN.
2. Native-MCP runtime-marker gebruikt contract v3, schrijft via `/system/Projectmanager/RuntimeEvidence` en hash alleen daadwerkelijk geladen Native-MCP-code.
3. Een wijziging in uitsluitend Projectmanager-bron verandert de Native-MCP expected fingerprint niet; een wijziging in geladen Native-MCP-bron doet dat wel.
4. `/project` blijft read-only; geen fingerprintwriter of runtime-evidence write naar `/project/Inbox/...`.
5. Finale PM-coordinatie gebruikt cycle-generation + FINAL provenance en mag niet uitsluitend door bekende NAS wall-clock skew RED worden.
6. Niet-gecoordineerde of structureel stale runtime blijft fail-closed.
7. Incoming -> Processing -> watcher/installatie -> runtime-validatie -> ACCEPTED blijft de enige releaseketen.
8. Alle reguliere tests GREEN; bekende skips blijven expliciet.
9. Release ZIP fresh-extract, CRC, member-safety, manifest en SHA256SUMS volledig verifiëren.
10. Productie blijft ongewijzigd tijdens de build/verificatie.

Historische vaste acceptatie-afspraken die behouden blijven:
- Gebruik GEEN Home Assistant Terminal.
- Gebruik GEEN handmatige Git-commit of Git-push.
- EPEX juli 2026 is gedeeltelijk; brondekking loopt in de historische testset tot 2026-07-29.
