# CURRENT HANDOVER — EnergieProject 32.5.24
## Integrated final — DS9/Spock + FULL_KB + Incoming closure

- Live predecessor: 32.5.23.
- Deze 32.5.24 vervangt alle eerdere 32.5.24-kandidaten en neemt de besproken DS9/Spock KB/PM/logging-, retentie-3- en command-proof-eisen integraal mee.
- Runtime moet alle Requirements dynamisch ontdekken en FULL_KB alleen COMPLETE noemen als rapportage-KB, technische PM-KB, Requirements, Handover, hoogste checkpoint/runtime, Master Development Index en bij ontwikkeling PROJECT_AFSPRAKEN + CHANGELOG aanwezig zijn.
- PM schrijft runtime development-context v2 en synchroniseert Master Development Index + Ledger Current Truth met readback; conflict tussen live/checkpoint/status is fail-closed.
- Artifactretentie = 3; nieuwste officiële releasenaam, oudere `previous_*`; geen suffix-bestand naar Incoming.
- Huidige live recovery vóór plaatsing van de nieuwe ZIP: uitsluitend het begrensde `release_32524_incoming_tunnel.sh`-pad, met lege Incoming/Processing en exact-current-state preflight.
- Tunnel moet de watcher/ReleaseController eerst quiescent maken vóór carrier/source-replacement; daarna dubbele SHA-readback met race-window. Dit voorkomt dat live 32.5.23 source-sync de nieuwe bootstrap terugdraait.
- Dangerous/protected stop/start/recreate blijft expliciete approval-gate; algemene `verder` is geen approval.
- Na tunnel GREEN gaat exact één officiële 32.5.24-ZIP naar Incoming en moet de normale keten zonder handmatige move eindigen in live 32.5.24 + Processed.
- Geen Type-2 destructive actie in deze release-installatie.

# CURRENT HANDOVER — EnergieProject 32.5.24 replacement

## Current live truth before replacement install
- Historische release-statusspiegel `Inbox/release_controller/current.json` blijft alleen compatibiliteitsevidence; canonieke runtime/readback blijft leidend.
- Runtime-statusautoriteit: actuele live runtime/readback gaat altijd vóór statische handovertekst of oudere checkpoints.
- 32.5.23 reached COMPLETE 9/9; PM rc56.
- Exact 32.5.23 artifact SHA256 `a1238939297dec600a0e5b6c9519ac7c7ed9651b80c515418c7a526af60c8e09`.
- Legacy `Inbox/control_plane/runtime.json` remained the active writer while canonical `ControlPlane/Runtime/runtime.json` was stale.
- ClearUp_007 live validation therefore remained RED.
- The previous 32.5.24 candidate SHA `3d2ce89c45afdd9a67879ea7ce46f81a7d2202292067e6bb92b0bf923b43e2aa` is SUPERSEDED and must not be installed.

## Replacement 32.5.24 scope
- Retain N+1 activation carrier so predecessor-loaded 32.5.23 code executes the control-plane binding proof during the 32.5.24 transition.
- PM rc58 implements the two 32.5.24 hard-requirement sets: live truth/closure plus progress/release-regie/Type-2 closure.
- Historical Type-2 recovery receipt and current-set integrity are separate. Receipt must never regress to “not received”; changed current bytes remain a concrete fail-closed integrity blocker.
- Full 002–012 E2E acceptance now includes practical restore and release-mailbox preservation.
- LIVE_REQUIRED cannot close without LIVE_PROVEN, including task completion.
- Step X/Y + elapsed/ETA and exceptional terminal metadata are technically enforced.
- PM flags version stacking/carry-forward.

## Source acceptance
- 147/147 32.5 GREEN.
- 72/72 broader PM/handoff/build-contract GREEN.
- 600/600 static GREEN + 2 skipped.
- 165/165 complete current 32.5 family GREEN after QNAP root/tunnel correction.
- compileall GREEN.

## After exact replacement install
1. Require release COMPLETE 9/9, NAS/HA 32.5.24 and PM rc58 runtime proof.
2. Prove canonical ControlPlane heartbeat fresh and legacy Inbox/control_plane quiescent.
3. Revalidate ClearUp_007 through real CommandIngress -> PM -> privileged watcher and require GREEN.
4. Reconcile all 002–012 current plan/recovery/validation truth.
5. Recovery receipt remains confirmed; if current recovery bytes differ from the previously delivered set, report only the exact changed-set blocker and deliver/prove that current set before delete.
6. Record required PM live acceptance (including new_chat_verder_e2e) as LIVE_PROVEN before functional COMPLETE.
7. Only after every current destructive gate is exact may live finalize/delete proceed; then prove legacy sources absent, canonical destinations present and release mailboxes intact.

## 32.5.24 live-boundary correction
- Real incoming exposed a predecessor runtime blocker before 32.5.24 could be consumed.
- Root cause: desired recreated control-plane correctly kept `ReleaseController` read-only, but bootstrap still attempted to atomically write its security marker inside that read-only mount.
- Replacement 32.5.24 preserves the read-only security boundary and routes only that marker to `/control-plane-runtime`, which is already the canonical writable runtime mount.
- Do not weaken the release-controller bind to rw.

- Final parser-boundary fix: the bootstrap consumes `--security-root` before calling the existing control-plane parser; otherwise the correct mount fix would still fail at process startup.


## 32.5.24 pre-install tunnel correction — 27-09-2026
- Vorige tunnelcommand met `cd /share/Energie_NAS/EnergieProject` is REJECTED; dat pad bestaat niet als QNAP-hostdirectory in de actieve omgeving.
- Geen protected mutatie uitgevoerd door die mislukte commandopoging.
- QNAP bootstrap in de nieuwe candidate accepteert de bewezen host aliases en heeft SHA256 `daf47911d307b8c8ffc9f4a3f7eb993e41df1e8f50c4e81fd4148ae289ca62e0`.
- Tunnel source is hersteld: stale pre-fingerprint `0dc5...`; gewenste post-fingerprint `bba109...`; exact recovery-carrier wordt eerst geplaatst met rollback-copy.
- Oude tunnel SHA `143e9165...` en approval daarop zijn SUPERSEDED. Nieuwe exact-script SHA wordt pas na finale rebuild/audit als uitvoerbaar vastgelegd.
