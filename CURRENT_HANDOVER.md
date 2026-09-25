# CURRENT HANDOVER — EnergieProject 32.5.9

32.5.9 is a clean rebuild from the exact physical 32.5.8 release artifact. The withdrawn 32.5.9 artifact with SHA256 71dc599a9c1a8961238ecf87b41df8b84aa89d45c2d8b50efb236d6b4dedb95a was used only as an audit reference and is superseded.

Current release objectives:
- prevent historical Native-MCP/control-plane state from blocking a current incoming release;
- migrate/validate the Native-MCP registry annotation contract before activating `tools_clearup_export.py`, so an old registry can never cause the MCP container to enter a restart-loop;
- permit only exact release-scoped COMPLETE-phase Native-MCP reconciliation when release_id, generation, artifact SHA, release version and expected runtime fingerprint all match;
- keep manual/native restart paths protected and require explicit Peter approval;
- keep retired legacy state as evidence only from 32.5.9 onward;
- provide executable ClearUp Type1 and Type2 002..012 routes via CommandIngress -> Projectmanager -> sideband -> privileged executor;
- preserve all four release mailboxes during ClearUp Type2 operations.

Release validation is artifact-specific. No live production state is claimed by this static handover.
## Bindende release-overdracht naar iedere volgende chat

Deze regels moeten door iedere nieuwe chat als vaste projectwerkwijze worden overgenomen:
- ChatGPT bouwt en audit exact één fysieke release-ZIP en biedt die **in de chat als downloadlink** aan.
- ChatGPT plaatst een release-ZIP **nooit zelf** in NAS `Inbox/incoming`. Peter downloadt exact de aangeboden ZIP en plaatst hem zelf in `Inbox/incoming`.
- De ChatGPT Library is geen normale release-afleverroute en vervangt de downloadlink in de chat niet.
- Vóór aanbieden moet exact de downloadbare ZIP fresh-extract zijn getest, inclusief ZIP-integriteit, manifests, actuele release-regressies, Incoming `voorganger -> incoming -> processing`, en waar van toepassing ClearUp Type1 + Type2 002..012.
- Na Peters melding dat de release draait, voert ChatGPT automatisch de post-live audit uit.
- Deze regels moeten expliciet in elke volgende handover blijven staan; een nieuwe chat mag ze niet opnieuw laten afhangen van Peters herinnering.

