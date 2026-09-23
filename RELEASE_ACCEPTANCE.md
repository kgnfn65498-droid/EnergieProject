# Release Acceptance — 32.4.66

Release Acceptance toetst de productie-releaseketen en de V66 observability-fix.

Verplicht:
- exact V65 predecessor artifact `e00a7fc0dfc81d3dfe7dbac6bac3cef213a987f207ad4d0d62588450b0bc9152` en byte-exact predecessor `main.py` `35814b8555f2d50078ba9fcb77324b76a635530ce31f79cd1585b63463df018c`;
- predecessor publiceert V66 exact en roept na publicatie alleen `/store/reload` aan;
- geen automatische HA update/install/rebuild;
- GitHub exact + HA predecessor => `WAITING_MANUAL_HA_UPDATE` en artifact blijft Processing;
- exact HA V66 => contract unlink + exact Processed archive + COMPLETE;
- na settlement wordt `github_publication_state.json` controller-authoritative bijgewerkt met:
  - `publication_contract_removed=true` (legacy compatibility),
  - `publication_contract_settled=true`,
  - `publication_contract_active=false`,
  - `contract_settled_by=release_controller`,
  - exact release_id/generation settlement fencing;
- CURRENT_HANDOVER bevat geen mutable DEVELOPMENT/WAITING/COMPLETE-statusclaim;
- V66→synthetische V67 N+1 contract GREEN.

Platform Qualification blijft apart; bekende restricted-host failures buiten de actieve releaseketen worden niet verborgen en niet als release GREEN geclaimd.
