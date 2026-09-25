## Release 32.5.10

32.5.10 is a bounded structural repair for ClearUp Type2 validation on NAS. It removes the embedded-PM permission dependency for validation evidence and closes the watcher result/timeout race. All 32.5.9 release-chain and safety guarantees remain binding.

## Release 32.5.9
Native MCP command-bridge activation fix voor ClearUp Type 1/2.

# EnergieProject 32.4.44

32.4.44 is de structurele reparatiebuild na de live-audit van 32.4.43. De prioriteit is dat de bestaande releaseketen `Incoming -> watcher -> runtime -> self-audit -> ACCEPTED` niet opnieuw handmatig hoeft te worden gerepareerd.

## Hoofdreparaties

- Native MCP runtime-fingerprint heeft één eigenaar: `runtime_fingerprint.py` v2 schrijft uitsluitend via de schrijfbare `/system`-mount. De oude v1 import-time writer naar read-only `/project` wordt uit de CR-hotfix verwijderd.
- Een oude control-plane `native_mcp_reload` request van een vorige release wordt alleen bij een aantoonbaar geldige stale releasebinding veilig gearchiveerd; conflicten binnen dezelfde release blijven fail-closed.
- Finale Projectmanager-coördinatie ververst de heartbeat vlak vóór self-audit, zodat een lange cyclus geen foutieve `stale heartbeat` RED veroorzaakt.
- Oude MAINTENANCE closure-taken worden door autoritatieve nieuwere runtime/atomic state gesupersedeerd.
- Het historische `commands:interrupted_after_restart` issue wordt alleen gesloten wanneer de canonieke command queue aantoonbaar geen `INTERRUPTED` commands meer bevat.
- De bestaande autonome closure-volgorde blijft: actuele Project CR -> NAS Container CR -> CLEARUP -> closure GREEN.

## Buildbasis

Exact de door Peter aangeleverde en opnieuw geverifieerde `EnergieProject_v32.4.43.zip`:

`f1a4352a78ea2daf10359603fc4bd94c68b1f50d9f19694848adbb4ac28c54ec`

Zie `docs/32.4.44-build-basis.json`.

## Governance

Geen alternatieve releaseweg, geen reconstructie vanaf productie en geen automatische productieplaatsing. De ZIP wordt eerst geïsoleerd gebouwd en geverifieerd; productieplaatsing blijft een aparte expliciete handeling.
## ClearUp 32.5.7

32.5.7 bevat naast de begrensde ClearUp_001 TYPE1-delete ook de concrete TYPE2-plannen `ClearUp_002` t/m `ClearUp_012`. TYPE2 maakt eerst herstelbare recovery, migreert daarna naar definitieve `Data/03_Systeem/Projectmanager/...` locaties met de oude bron nog aanwezig, vereist live reader/writer-validatie en verwijdert de oude bron pas na een tweede expliciet akkoord. De release-mailboxen `incoming`, `processing`, `processed` en `failed` zijn uitgesloten. Geen terminal of handmatige Inbox-bypass is onderdeel van de ClearUp-route.

