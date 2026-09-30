## 32.5.30 — deterministic context + ROOT cleanup + release-chain hardening

- Completes the 32.5.30 development scope around deterministic Projectmanager/Knowledge Base/Master Index context, with final NAS staging still authoritative for that subsystem.
- Adds canonical top-level `Rollback/` for 32.5.30+ release swaps while keeping historical releases backward-compatible; newest three rollbacks are retained.
- Adds guarded ROOT cleanup commands (inventory, preview, recovery, export/confirm, apply, restore, finalize) through the existing privileged ClearUp sideband; non-rollback deletion remains recovery-first.
- Moves 32.5.30+ ClearUp quarantine below `Data/03_Systeem/Projectmanager/ClearUp/Quarantine` so normal cleanup no longer recreates top-level `CLEARUP`.
- Hardens the 32.5.29 ingress failure modes: build-time exact release-identity validation, build-time publisher system-path import validation, and a bounded split-state pre-target publication wait while preserving the intentionally unbounded manual Home Assistant update wait.
- Native MCP `/project` root-alias and health-dashboard scan fixes remain part of the authoritative NAS 32.5.30 staging and require live validation after install.
- Development branch only; no release/merge claim until exact predecessor-ZIP build, fresh-extract tests and live acceptance are GREEN.

## 32.5.29 — final Inbox recovery cross-identity writer contract

- Repairs the live 32.5.28 blocker where `Projectmanager/Handover` and `ClearUp/{Recovery,Exports,State}` existed as 0755 and the embedded PM identity could not create atomic temp files or the final Inbox recovery artifact.
- The privileged ReleaseController now normalizes only these four exact shared writer directories to 0777 after a completed 32.5.29 release, rejects symlinks/non-directories, and verifies mode readback.
- No new ClearUp executor, no Type-2 reopen, no Inbox bypass, no delete-before-recovery. Existing 32.5.28 recovery-first confirmation and final Inbox cleanup logic remains unchanged.

# Changelog

## 32.5.28 — recovery-first final Inbox cleanup + always-current handover
- Adds pre-mutation recovery packaging/export for the final Inbox cleanup, with source SHA256 manifest, deep ZIP verification, bounded chunks and exact external-confirmation gating.
- Privileged cleanup apply revalidates current plan, recovery ZIP and live source bytes immediately before mutation; stale/mutated recovery evidence fails closed.
- Re-proves the release standard `Incoming -> processing -> HA exact -> processed` for two consecutive releases while preserving the permanent Processing mailbox.
- Adds exact 32.5.27 predecessor-boundary proof: the unchanged predecessor release-path bytes claim 32.5.28 from Incoming and archive only after exact HA target settlement.
- Adds automatic development-handover generation/freshness reconciliation; stale pointer/handover/checkpoint truth blocks release-ready and ManagerService self-heals partial generations.
- PM target `2.0.0-rc63`; Type-2 002–012 remains CLOSED.
