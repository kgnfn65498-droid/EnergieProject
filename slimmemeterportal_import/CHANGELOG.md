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
