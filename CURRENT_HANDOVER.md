# CURRENT HANDOVER — EnergieProject 32.5.28
## Recovery-first final Inbox cleanup + always-current handover

Buildbasis: exact `EnergieProject_v32.5.27.zip`, SHA256 `ea3674ebc32067a7c71b5798f33cb3e9de03f1d1c178dcb96e0f73e7dc4e89f2`. Live productie blijft 32.5.27 totdat de normale Incoming-keten 32.5.28 volledig heeft verwerkt. Type-2 ClearUp_002–012 blijft CLOSED.

32.5.28 voegt vóór de finale Type-3/Inbox-cleanup een recovery-first grens toe: exact cleanupplan -> pre-mutation payloadsnapshot -> manifest/source hashes -> recovery ZIP -> deep verify -> bounded export -> exacte externe bevestiging. Zonder die bevestiging kan live apply niet starten. De bestaande sideband + `project_clearup_move_executor.py` blijven de enige privileged filesystem-boundary; er is geen derde executor.

De releaseketen blijft bindend: `Incoming -> processing -> HA exact -> processed`. Processing is permanent en idle aanwezig/leeg. De 32.5.27 releasepadmodules zijn byte-identiek gebleven en de predecessor-boundary bewijst dat een 32.5.28-kandidaat Incoming verlaat, in Processing wacht zolang HA nog 32.5.27 is en pas na exacte HA-target met dezelfde SHA256 naar Processed gaat.

Development continuity is vanaf 32.5.28 technisch fail-closed: checkpoint, current pointer en current handover voeren één generation/fingerprint. Stale/missing/mismatch blokkeert release-ready; ManagerService herstelt een half bijgewerkte generatie autonoom. Nieuwe-chat `verder` hervat vanaf de nieuwste geldige checkpoint-truth.

Runtime-statusautoriteit: mutable live status komt uitsluitend uit `Inbox/release_controller/current.json` en de canonieke runtime/state-readback; dit statische handoverdocument claimt geen mutable live Status.

Na installatie blijft de finale live ClearUp geblokkeerd totdat de recovery-ZIP in chat is geleverd/gedownload en exact extern is bevestigd. Daarna: cleanup, 20 s resurrection soak en post-cleanup audit.
