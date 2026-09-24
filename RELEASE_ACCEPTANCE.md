# Release Acceptance — 32.5.6

Verplicht voor deze release:
- `VERSIE.txt`, Home Assistant `config.yaml`, `APP_VERSION`, `TARGET_RELEASE_VERSION` en `release_test_contract.CURRENT_RELEASE` zijn exact `32.5.6`;
- fysieke ZIP is veilig, uniek en volledig; `MANIFEST.sha256` en `SHA256SUMS.json` dekken exact dezelfde payload en iedere hash klopt;
- `.pytest_cache`, `__pycache__`, bytecode, `.DS_Store`, tijdelijke herstelbestanden en 32.5.4 PATCH/RECOVER-noodscripts zitten niet in de release-ZIP;
- productie-preflight uit 32.5.4 én target-preflight uit 32.5.6 accepteren exact dezelfde fysieke kandidaat;
- lokale installatie-predecessor en canonieke GitHub/HA-publicatiepredecessor zijn afzonderlijke contractdomeinen en mogen aantoonbaar verschillen na partial publish + rollback;
- split-state `local N + GitHub/HA N+1 + rollback + N+2` publiceert en installeert zonder tijdelijke versie-impersonatie, directe state-edit of terminalrecovery;
- canonical publisher valideert in split-state zowel lokale App+manifest als GitHub+HA predecessor exact;
- exact gepubliceerde pre-target targetidentiteit blijft onveranderd door lokale installatie en handmatige HA-update; geen post-install `publication_contract_conflict`;
- een bewezen stale contract van een exact rolled-back release wordt atomair gearchiveerd en vervangen; vreemde/onbewezen contracten blijven fail-closed;
- Processing blijft eigenaar tot exact GitHub-target + exact HA-runtime + controller settlement; pas daarna verhuist het artifact naar Processed;
- Home Assistant update blijft expliciet handmatig; publisher gebruikt geen automatische install/rebuild-bypass;
- COMPLETE genereert `Inbox/release_controller/post_live_audit.json` en 32.5.6+ sluit niet GREEN bij een RED post-live audit;
- een settled IDLE releasecontroller is health-GREEN en wordt niet foutief als stale/liveness-RED geclassificeerd;
- normale releaseketen heeft geen QNAP-, Home Assistant- of containerterminal nodig;
- gevaarlijke live hotpatch/recovery-commandoklassen zijn geen normale releasedependency en vereisen expliciete Peter-toestemming buiten de releaseketen.

## Verificatie
De finale fysieke ZIP moet na fresh extract opnieuw worden getest. Release-focused regressies, packaging/preflight-pariteit en compile/audit moeten GREEN zijn voordat de ZIP wordt aangeboden.

Platform Qualification blijft apart. Repository-wide full-suite GREEN wordt uitsluitend geclaimd wanneer die suite op de daarvoor goedgekeurde geïsoleerde runtime volledig GREEN draait; bekende restricted-host/historische testtopologie wordt niet stilzwijgend als release-GREEN gepresenteerd.
