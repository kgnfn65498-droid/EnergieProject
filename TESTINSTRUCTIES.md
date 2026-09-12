# Testinstructies v32.4.48 — definitieve 32.4 closure hardening

1. TDD RED reproduceren voor de vier live bevindingen: archive-permission, stale PM-taak, stale releasebeslissing en ontbrekende semantische self-audit.
2. GREEN: stale control-plane request archiveert uitsluitend onder `Inbox/projectmanager_v2/RuntimeV2/control_plane_archive`.
3. GREEN: oudere versiegebonden DEVELOPMENT/closure-taak wordt door nieuwere live runtime + atomic evidence gesupersedeerd.
4. GREEN: oudere Native-MCP PRODUCTION_RESTART decision/WAITING_APPROVAL command wordt bij nieuwere live release veilig gesupersedeerd/geannuleerd; actuele releasebeslissing blijft backup/fallback zolang runtime niet GREEN is.
5. GREEN: self-audit rapporteert `active_task_release_older_than_runtime` wanneer een stale actieve taak toch ontsnapt.
6. Peters standing authorization blijft alleen gelden voor exact releasegebonden `projectmanager_auto` Native-MCP self-heal na ACCEPTED release.
7. Volledige regressie, compile, shellsyntax, exact artifact builder, verse ZIP-extractie, CRC, manifest en SHA256SUMS verifiëren.
8. Productie blijft tijdens build/verificatie ongewijzigd.

Live na installatie: Native MCP expected==runtime, actuele Project/NAS CR, CLEARUP/hygiene en volledige 32.4 acceptance matrix opnieuw controleren.

Historische vaste acceptatie-afspraken die behouden blijven:
- Gebruik GEEN Home Assistant Terminal.
- Gebruik GEEN handmatige Git-commit of Git-push.
- EPEX juli 2026 is gedeeltelijk; brondekking loopt in de historische testset tot 2026-07-29.
