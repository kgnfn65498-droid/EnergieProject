# CURRENT HANDOVER — EnergieProject 32.5.30
## Deterministic context + release-chain handover

Buildbasis: exact EnergieProject_v32.5.29.zip, SHA256 bfc9cd1cbbddbafaeb4ef2546ad0c7592f2b135d5d3324df5bf9d4963282f146. Target release: 32.5.30; Projectmanager target: 2.0.0-rc64.

De releaseketen blijft bindend: Incoming -> processing -> GitHub/publication proof -> handmatige Home Assistant update -> HA exact -> processed. De handmatige Home Assistant grens blijft expliciet; deze release voegt geen autonome HA-update toe.

Projectmanager, Knowledge Base, Master Index, current pointer en checkpoint vormen één fail-closed contextketen. Nieuwe-chat/verder hervat uitsluitend uit actuele canonieke truth met geldige mandatory context; optional evidence mag geen geldige mandatory context ongeldig maken.

Release-ingress recovery is begrensd en single-owner: alleen ondubbelzinnige Incoming/Processing-states mogen autonoom herstellen; ambiguïteit blijft BLOCKED.

Runtime-statusautoriteit: mutable live status komt uitsluitend uit Inbox/release_controller/current.json en aanvullende live readback. Dit statische handoverdocument bevat geen mutable live statusclaim.
