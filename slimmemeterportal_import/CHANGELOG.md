# Changelog

## 32.5.27 — persistent Processing mailbox + canonical publication writer contract
- Corrects the 32.5.26 Processing-model defect: `Inbox/processing` is a permanent mailbox in `incoming -> processing -> processed`; only the release ZIP leaves it after settlement, the empty directory remains.
- Post-live acceptance now requires Processing to exist, be a real directory and be empty; final Type-3/Inbox cleanup is forbidden from removing it.
- ReleaseController, HA delivery and ingress recovery all preserve/recreate the permanent Processing mailbox.
- Hardens the canonical ClearUp_011 publication destination for cross-identity HA writes: `ReleaseController/Publication` is normalized to directory mode `0777` and existing publication-state files to `0666` at completed-release reconciliation, without any fallback to Inbox.
- Keeps GitHub publication state exclusively at the canonical `Data/03_Systeem/Projectmanager/ReleaseController/Publication` location.
- PM target `2.0.0-rc62`; Type-2 002-012 remains CLOSED.
