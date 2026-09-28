# CURRENT HANDOVER — EnergieProject 32.5.26 PRE-INSTALL
## Autonomous Processing→Processed + originele Type-3/finale Inbox-cleanup

Buildbasis: exact `EnergieProject_v32.5.25.zip`, SHA256 `bc667f11d6a22ef4588add6c213baff21c5b7ebd6591e5b4820732d5a9bbaf4a`. Live 32.5.25 is COMPLETE; ClearUp Type-2 002–012 is 11/11 definitief GREEN en wordt niet opnieuw uitgevoerd.

32.5.26 gebruikt voor Type-3/finale Inbox-cleanup uitsluitend de bewezen **32.5.x** request-scoped privileged sideband/executorarchitectuur. `inbox_cleanup_32526.py` bouwt een exact hash-bound plan en vraagt uitvoering aan; alleen `sideband_bridge.py` + `project_clearup_move_executor.py` muteren de live tree. De oude 32.4 `project_clearup_auto` startup-route is voor deze opdracht HISTORICAL/FORBIDDEN en wordt niet gereactiveerd.

De finale Inbox-scope is: `failed` plat; `release_hold_tmp` + historische publication/HA-restanten weg; crash-cleanup en publisher-lock eerst canoniek omgebonden; `processing` alleen transactioneel en na closure afwezig; `Inbox/projectmanager_v2` als allerlaatste na consumed-receipt bewijs. Alle mutaties zijn bounded, plan-fingerprinted, request-scoped en reversibel via CLEARUP/restore; resurrection tijdens soak = RED + rollback.

De Projectmanager krijgt capability-provenance in development context/handover. Een nieuwe chat moet die capabilitykaart raadplegen vóór de conclusie dat een executor/route ontbreekt. Daarmee wordt ook het hier gevonden continuity-defect structureel afgesloten.

Live-only na installatie: echte Processing→Processed closure, finale Inbox inventory/apply, writer-reappearance soak, tree-readback, retained ZIP retrieval en nieuwe-chat `verder` E2E. Geen handmatige ZIP-move of publication-state-reconciliatie als normale route.

---

# CURRENT HANDOVER — EnergieProject 32.5.25
## Type-2 fysieke closure + DS9/Spock continuïteit

Deze statische handover bevat uitsluitend de releasecontracten; **Runtime-statusautoriteit** blijft de actuele runtime/readback. `Inbox/release_controller/current.json` is een compatibiliteitspad dat via het Type-2 system-path-contract naar de canonieke ReleaseController-state resolveert zodra die mapping actief is.

## Doel van 32.5.25
- Alle legacy Type-2 bronnen `ClearUp_002` t/m `ClearUp_012` moeten na finalize fysiek verdwijnen.
- Geen actieve writer mag een verwijderd legacy pad opnieuw aanmaken.
- Iedere finalize bewijst bron-afwezigheid én behoud van de canonieke bestemming gedurende een post-delete soak; reappearance = RED.
- De huidige extern bevestigde recoveryset blijft de recoverybasis; finalize blijft exact plan/recovery/validation-gated.

## Structurele reparaties
- Native-MCP runtime-contract hotfix en CR-standard hotfix schrijven na activatie uitsluitend via `project_system_path` naar canonieke logs.
- De GitHub-publisher krijgt canonieke `Data/03_Systeem` + `system_path_contract.sh` mounts. ReleaseController 32.5.25 controleert/recreëert de legacy publisher-binding automatisch na COMPLETE en rolt terug bij mislukking.
- Embedded PM reconcileert Type-2 external-recovery truth read-only; alleen de privileged watcher mag de protected recovery-gate persistent wijzigen.
- Type-2 finalize voert hard-move/delete/readback uit en bewaakt daarna standaard 20 s op source reappearance terwijl alle destinations aanwezig moeten blijven.

## DS9 / Spock / Knowledge Base
32.5.25 dwingt FULL_KB technisch af. Verplicht zijn beide KB-roots, alle dynamisch ontdekte Requirements, actuele Handover, hoogste checkpoint, Master Development Index, Active Context, Development Manifest, Unified Ledger, Ledger Current Truth, **Decision Log**, **Development Changelog**, **Spock Context**, Full-KB audit, Ticket/Issue Index, KB Inventory, PROJECT_AFSPRAKEN en App CHANGELOG.

De canonieke administratieve router blijft `00_MASTER_DEVELOPMENT_INDEX.md`; er wordt geen parallelle projectwaarheid gemaakt.

## Nieuwe chat
De runtime bouwt `new_chat_preflight` fail-closed. Alleen wanneer FULL_KB COMPLETE, truth reconciliation GREEN, live release aanwezig en hoogste checkpoint bekend zijn geldt:
- `ready=true`;
- `manual_reexplanation_required=false`;
- `resume_command=verder`;
- pointers naar Master Index, Active Context, Ledger Current Truth, Decision Log, Development Changelog, Spock Context, Ticket/Issue Index en KB Inventory aanwezig.

Een nieuwe chat met alleen **`verder`** moet daarom vanaf de laatst bewezen live waarheid hervatten. Dit wordt na live installatie nog één keer E2E bewezen; vóór die live proef is het PRE-INSTALL bewezen maar niet LIVE_PROVEN.

## Releasegrens
- Buildbasis: exact geverifieerde 32.5.24 artifact SHA256 `cb1b503606ad99f7b3796f3856c58da7c6066a45f4d375efdfd5d8f36e36701b`.
- PM target: `2.0.0-rc60`.
- Oude 32.5.25 artifact SHA256 `85557cb336c1ca46242ba614f5df8f7db808fbbcab99961b0d4b856cc8473c64` is **SUPERSEDED / NIET INSTALLEREN**.
- Finale 32.5.25 artifactidentiteit wordt uitsluitend door het externe finale pre-install checkpoint vastgelegd nadat exact fresh-extract volledig GREEN is.
- De installatie zelf verwijdert geen Type-2 bron. Na live 32.5.25 COMPLETE volgt writer-binding/quiescence-readback, fresh 002–012 validation, daarna de reeds goedgekeurde sequentiële finalize 002→012, stop-on-first-RED, gevolgd door een globale absence-soak.
## Runtime task/checkpoint reconciliatie
- De hoogste `energie_chat_switch_checkpoint_v2` is machine-authority voor een expliciet als stale gemarkeerde actieve taak.
- Zodra exact `target_release=32.5.25` live is, geldt `live_release=32.5.24` in die pre-install checkpoint niet als conflict maar als bewezen target-reached overgang.
- De stale ClearUp_001-taak wordt dan met checkpoint-evidence `SUPERSEDED`; als geen actuele taak resteert wordt één 32.5.25 DEVELOPMENT closure-taak hervat met `new_chat_verder_e2e` en writer/Type-2 closure als next action.
- Een willekeurige checkpoint/live mismatch blijft fail-closed; deze uitzondering geldt uitsluitend voor het exacte READY_FOR_NEW_CHAT target-reached contract.

