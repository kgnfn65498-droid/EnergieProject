# Changelog

## 32.5.16 — Type-2 volledige herstel- en migratiehardening

- ClearUp_002 recovery kan veilig hervatten na post-cutover RuntimeV2-drift.
- PREPARED recovery-ZIP's worden vóór migratie opnieuw gesnapshot en cutover-recovery wordt vóór path-activation bevroren.
- Type-2 paden 002–012 gebruiken na activatie de canonieke systeemlocaties; retired Inbox-paden worden niet opnieuw aangemaakt door de aangepaste runtimecomponenten.
- Externe recoverybevestiging blijft verplicht vóór iedere destructive finalize/delete.
- Control-plane runtime blijft compatibel met de bestaande container-mounts en schrijft na migratie niet terug naar retired PM/native Inbox-routes.

## 32.5.15 — ClearUp recovery delivery closure

- Type-2 recovery: veilige post-migrate refresh voor een bewaarde bron; bron en gemigreerde bestemming blijven onaangeroerd.
- Recovery-ZIP-verificatie controleert elk payloadbestand op manifestgrootte en SHA-256.
- Een defecte recovery-ZIP blokkeert de downloadlinks van de overige geverifieerde ZIPs niet meer.
- Native MCP gebruikt de canonieke `Data/03_Systeem/Projectmanager/RuntimeV2`; de oude Inbox-runtime is een retired alias.
- Control-plane release-authority is onafhankelijk van een stale losse `App/VERSIE.txt` bind; toekomstige recreates bevatten die bind niet meer.
- Geen Type-2 delete/finalize; externe recoverybevestiging blijft verplicht.

## 32.5.14 — release-scoped Native-MCP authority

- Herstelt de control-plane race na atomic App-swap: release-scoped Native-MCP reload gebruikt de bestaande release-controller + atomic-state in Inbox als autoriteit, niet de inode-stale losse VERSIE bind.
- Geen nieuwe paden, services of ClearUp-opslagstructuur.

## 32.5.13 — Type2 recovery download bridge

- Uses the existing Projectmanager status surface and existing ClearUp export path to expose short-lived signed recovery ZIP download links.
- No new MCP tool name, no new storage path and no destructive ClearUp action.

## 32.5.12 — Type2 privileged quiescence authority

- Privileged watcher performs the final two-snapshot old-source quiescence proof and commits its stable source hash.
- PM-observed source hash is retained as audit metadata rather than used as cross-process identity fencing.
- Finalize still refuses any post-validation source change.
- Existing ClearUp_002 migrated state and ClearUp_002..012 recovery exports remain resumable without re-prepare or re-migrate.
