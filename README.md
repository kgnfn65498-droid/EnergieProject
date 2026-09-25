## Release 32.5.14

32.5.14 is een minimale control-plane correctie op 32.5.13. De release voegt geen nieuwe paden of services toe. Hij voorkomt dat een inode-stale Docker file-bind van `App/VERSIE.txt` een geldige release-scoped Native-MCP reload als stale archiveert. Voor die release-scoped route zijn de reeds bestaande `Inbox/release_controller/current.json` en `Inbox/atomic_app_swap_state.json` de autoriteit.

De Type-2 recovery-ZIP's blijven onder `Data/03_Systeem/Projectmanager/ClearUp/Exports`. De 32.5.13 downloadbrug via de bestaande `projectmanager_status`-tool blijft ongewijzigd aanwezig. Geen Type-2 delete/finalize vóór externe download + SHA-verificatie + expliciete bevestiging.
