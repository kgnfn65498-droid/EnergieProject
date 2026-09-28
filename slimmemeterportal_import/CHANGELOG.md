# Changelog

## 32.5.28 — recovery-first final Inbox cleanup + always-current handover
- Adds pre-mutation recovery packaging/export for the final Inbox cleanup, with source SHA256 manifest, deep ZIP verification, bounded chunks and exact external-confirmation gating.
- Privileged cleanup apply revalidates current plan, recovery ZIP and live source bytes immediately before mutation; stale/mutated recovery evidence fails closed.
- Re-proves the release standard `Incoming -> processing -> HA exact -> processed` for two consecutive releases while preserving the permanent Processing mailbox.
- Adds exact 32.5.27 predecessor-boundary proof: the unchanged predecessor release-path bytes claim 32.5.28 from Incoming and archive only after exact HA target settlement.
- Adds automatic development-handover generation/freshness reconciliation; stale pointer/handover/checkpoint truth blocks release-ready and ManagerService self-heals partial generations.
- PM target `2.0.0-rc63`; Type-2 002–012 remains CLOSED.
