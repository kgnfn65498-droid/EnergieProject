# Release Acceptance — 32.5.21

Status: READY_FOR_USER_INCOMING

## Scope
1. Herstel de live ClearUp_005 vervolgroute wanneer `Data/03_Systeem/Projectmanager/ReleaseController` al bestaat doordat andere Type-2 mappings daar sibling `State/`/`Publication/` data hebben geplaatst.
2. Directory-migratie mag alleen veilig mergen: bestaande corresponderende paden moeten exact type/byte-identiek zijn; niet-gerelateerde sibling data blijft onaangeraakt; rollback verwijdert uitsluitend door deze migratie nieuw aangemaakte paden.
3. Verplaats Type-2 filesystemvalidatie volledig naar de privileged watcher. De embedded PM hoeft privileged `native_mcp_runtime`/`control_plane` inhoud niet meer direct te lezen.
4. Behoud alle bestaande fail-closed gates: release idle, plan-hash, recovery ZIP, path activation, cutover paths, old-source quiescence, runtime writer proof en externe recoverybevestiging.
5. Geen Type-2 finalize/delete tijdens build/acceptance.

## Live bewijs dat 32.5.21 noodzakelijk maakt
- 32.5.20: ClearUp_003 migreerde; eerste validatie detecteerde terecht een nog lopende publisher-writer en faalde fail-closed; revalidatie werd GREEN.
- ClearUp_004, 008, 009, 010, 011 en 012 migreerden en valideerden GREEN.
- ClearUp_005 bleef PREPARED: `destination already exists: .../ReleaseController` nadat ClearUp_011 sibling subtrees had aangemaakt.
- ClearUp_006 validatie faalde onder embedded PM identiteit met `PermissionError ... Inbox/native_mcp_runtime/reload_result.json`.
- ClearUp_007 validatie faalde onder embedded PM identiteit met `PermissionError ... Inbox/control_plane/requests`.
- Geen finalize/delete uitgevoerd; bronnen zijn behouden.

## Tests
- Type-2/v32.5 suite: 131/131 GREEN (95 niet-v3259 + 36 v3259), 1 bekende duplicate-name warning.
- Static: 600/600 GREEN, 2 skipped.
- Nieuwe 32.5.21 regressies: shared-destination continuation + privileged full validation GREEN.
- Compileall source: GREEN.
- Fresh-extract suites, manifest/CRC/hash/safe-entry en exact atomic 32.5.20→32.5.21 moeten bij finale artifactbouw GREEN zijn.
