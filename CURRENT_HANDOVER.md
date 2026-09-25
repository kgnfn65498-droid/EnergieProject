# CURRENT_HANDOVER — 32.5.8

Doel: ClearUp_001 moet vanuit chat normaal werken: recovery-ZIP vooraf, Peter zegt `akkoord`, Projectmanager voert bounded delete uit zonder terminal en zonder de release-Inbox te raken.

32.5.8 repareert de 32.5.6 live permissiefout door de bestaande QNAP watcher-executor te gebruiken voor exact vier TYPE1-roots. Chat gebruikt bestaand `admin_update` transport met `classification_hint=clearup_apply`, zodat de Native-MCP submit-command allowlist niet gewijzigd of herladen hoeft te worden.

Na live installatie: automatische post-live release-audit; daarna ClearUp_001 uitvoeren met bestaand expliciet akkoord, resultaat/readback controleren en pas GREEN verklaren als de vier oude paden weg zijn en incoming/processing intact zijn.

32.5.8 bevat daarnaast de reeds geïnventariseerde concrete TYPE2-batches `ClearUp_002` t/m `ClearUp_012`. De plannen leggen per item bron, definitieve systeemlocatie, pad-key, reden en contractcheck vast. De scope omvat RuntimeV2, logs/publisherhistorie, operating mode, releasecontroller/status, HA/Native-MCP runtime-evidence, ControlPlane runtime/config, process-workspace, watcher-evidence, lokale CR-state, release/publication-state en runtime-locks/heartbeat.

De TYPE2-volgorde is bindend: prepare + recovery-ZIP -> Peter downloadt/bewaart -> expliciet akkoord -> migrate naar definitieve locatie met bron nog intact -> live reader/writer-validatie -> afzonderlijk akkoord -> finalize oude bron -> readback/no-recreation. `incoming`, `processing`, `processed` en `failed` zijn uitgesloten. Readers/writers schakelen uitsluitend via het geverifieerde `system_path_contract`; geen blind pad vervangen en geen terminalroute.
