# CURRENT HANDOVER — EnergieProject 32.5.27
## Persistent Processing mailbox + canonical publication writer contract

Deze statische handover bevat uitsluitend releasecontracten; **Runtime-statusautoriteit** blijft de actuele runtime/readback via `Inbox/release_controller/current.json` en de canonieke Type-2 system-path mapping.

Buildbasis: exact `EnergieProject_v32.5.26.zip`, SHA256 `e0ffa48b93e42b8ef09319775b1a54b8e25a9e7719a30d347762c1dcdeed71f5`. Type-2 ClearUp_002–012 blijft CLOSED en wordt niet opnieuw uitgevoerd.

32.5.27 corrigeert één live bewezen modeldefect uit 32.5.26: `Inbox/processing` is een permanente mailbox in de keten `incoming -> processing -> processed`. Na settlement verhuist alleen de ZIP; `processing` blijft bestaan en moet idle leeg zijn. Post-live audit en finale Type-3/Inbox-cleanup volgen voortaan dit contract en mogen de map niet verwijderen.

De door ClearUp_011 vastgelegde GitHub-publication-state blijft uitsluitend canoniek onder `Data/03_Systeem/Projectmanager/ReleaseController/Publication`. Er is geen fallback naar Inbox. Omdat de HA-publisher cross-identity atomisch schrijft via een tijdelijk bestand + replace, normaliseert de completed-release reconciliation de canonieke Publication-directory naar 0777 en bestaande statebestanden naar 0666, gelijk aan de bestaande gedeelde IPC-conventie.

De finale Type-3/Inbox-cleanup blijft dezelfde bewezen 32.5.x request-scoped sideband/executor gebruiken. `failed` wordt plat; legacy restanten worden bounded/reversibel verplaatst; `Inbox/projectmanager_v2` blijft de laatste cleanup-actie. `Inbox/processing` is expliciet uitgesloten van cleanup.

Release acceptance en host-capability Platform Qualification blijven gescheiden contracten. Platform Qualification is geen releasegate en bestaande tests worden niet verwijderd of verzwakt om een build GREEN te maken.

Live-only bewijs na installatie: exact releasepad, canonieke publication writer-permissions, post-live audit present+empty Processing, finale Type-3/Inbox-cleanup en resurrection soak. Geen handmatige ZIP-move als normale route.
