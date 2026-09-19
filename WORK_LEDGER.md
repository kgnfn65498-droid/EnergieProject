## 2026-09-19 — 32.4.58 repository-layout hotfix

- Live NAS 32.4.58 is atomic ACCEPTED; HA runtime blijft 32.4.57 omdat Supervisor geen update toont.
- GitHub-publicatie zelf bereikte main, maar repository bevatte naast de echte add-onconfig ook historische `tests/fixtures/legacy57/config.yaml`.
- Officiële HA-regel: Supervisor scant `config.yaml` recursief; dubbele gereserveerde naam is dus een echte repository-layoutfout.
- Structurele fix: historische fixture -> `config_legacy57.yaml`, alle referenties aangepast, `test_58_22` borgt exact één HA config.
- Corrected source-suite volledig GREEN: 1.954 passed, 2 skipped, 0 failed (1.956 totaal); watcher practical soak 6/6 GREEN.
- Een vergeten `test_v32456_release_identity.py`-referentie werd door de full-suite gevonden, daarna gecorrigeerd en exact rerun GREEN.
- Tussentijdse hotfix artifact SHA `373e7f0d...` is vervallen; nieuw final artifact + fresh-extract nog vereist.
- Geen live state-edit, restart/recreate of nieuwe releaseversie gebruikt om het probleem te maskeren.

## 2026-09-18 — 32.4.57 checkpoint 11

- Release-scoped Native-MCP uitvoering en reconcile zijn nu duurzaam en generation-fenced.
- Een gefencede RED wordt exact als BLOCKED gerapporteerd en opent geen tweede uitvoerpad.
- Control Plane herstel is bounded per verwachte fingerprint en blijft één actuatorroute.
- Control-Plane source-sync evidence staat canoniek onder Inbox/release_controller.
- PM-health voor 57+ behandelt verouderde CP-heartbeat als observability; fingerprint mismatch blijft RED.
- Handover blijft vanaf 57 controller-owned; oude release_transition is historisch.
- 15/15 genummerde required cases, 1 next-release case en 36 specifieke 32.4.57 architectuurtests aanwezig.
- Checkpoint-11 delta nog niet via pytest/full build/fresh-extract uitgevoerd; geen GREEN-claim.
- Geen productieactie of kandidaat-ZIP.

## 2026-09-18 — 32.4.57 checkpoint 11

- Native-MCP actuator nu volledig attempt-fenced: maximaal één automatische restart per exact request_id; daarna alleen readback/reconcile.
- Reconcile valideert opnieuw actuele release_id/generation/version/artifact/fingerprint-fence.
- Gefencede RED wordt door de centrale RuntimeCoordinator exact BLOCKED als native_mcp_reload_unproven; geen nieuw request/restartpad.
- Control Plane bounded restart fence blijft maximaal één restart per expected fingerprint; nieuwe fingerprint mag één nieuwe bounded poging.
- Control-Plane source-sync evidence staat canoniek in Inbox/release_controller/control_plane_source_sync.json.
- PM-health voor 57+: stale/missing CP heartbeat is ORANGE observability; loaded fingerprint mismatch blijft RED; 55/56 contract ongewijzigd.
- Handover blijft voor 57 controller-owned; oude release_transition wordt historisch/leeg gemaakt.
- 15/15 genummerde required cases + 1 next-release case + 36 specifieke 32.4.57 architectuurtests aanwezig.
- Checkpoint-11 delta nog niet via pytest/full build/fresh-extract uitgevoerd; geen GREEN-claim.
- Geen productieactie, duplicaat 56-command, rescueketen of kandidaat-ZIP.

## 2026-09-18 — 32.4.57 checkpoint 10

- Native-MCP side effect is nu attempt-fenced: maximaal één automatische restart per exact request_id.
- RED/ATTEMPTING result blijft retry_allowed=false; latere exacte fingerprint kan hetzelfde request alleen reconcile-only naar GREEN brengen.
- Reconcile valideert opnieuw de actuele release_id/generation/artifact/version/fingerprint-fence.
- RuntimeCoordinator rapporteert exact gefencede RED als native_mcp_reload_unproven BLOCKED in plaats van eindeloos pending.
- Control Plane zelf heeft nu maximaal één bounded restart per exact expected fingerprint; zelfde fingerprint kan geen restart-loop vormen.
- Nieuwe expected CP fingerprint mag één nieuwe bounded restartpoging krijgen.
- Stale CP heartbeat + Docker healthy + exact loaded fingerprint blijft restart-vrij.
- Control-Plane source-sync evidence verplaatst van historische 32.4.44 marker naar Inbox/release_controller/control_plane_source_sync.json.
- Manual ProtectedActionExecutor kan een actieve 57 release-scoped native_mcp_reload niet overschrijven.
- Actieve 57 releasekern gescand op oude transition/hold/mode/CR/CLEARUP leakage: geen treffers.
- Testinventory: 15/15 genummerde required cases + 1 next-release case + 36 specifieke 32.4.57 architectuurtests aanwezig.
- Checkpoint-10 delta nog niet via pytest uitgevoerd; geen nieuwe GREEN-claim.
- Geen productieactie of kandidaat-ZIP.

## 2026-09-18 — 32.4.57 checkpoint 9

- Na retry/crash eerst persistent state gelezen: checkpoint 8 plus later gewijzigde staging tot 20:49:17Z teruggevonden; niet opnieuw begonnen.
- Control Plane pre-install/global sync verwijderd: Control Plane is nu uitsluitend actuator bij daadwerkelijke Native-MCP mismatch.
- Stale CP heartbeat is observability-only wanneer Docker healthy is en loaded fingerprint exact matcht; dan geen restart.
- Echte CP fingerprint mismatch kan maximaal één restart van de bestaande container uitvoeren; geen recreateketen.
- INSTALLING en RUNTIME_ALIGNING zijn nu aparte duurzame fasegrenzen vóór respectievelijke side effects.
- Crash na duurzaam atomic ACCEPTED maar vóór controller-state-save is idempotent herstelbaar; ACCEPTED App wordt niet teruggerold.
- Ontbrekende IngressDecision-import in orphan Processing route gerepareerd.
- Legacy adoption begrensd tot exact 32.4.56 -> 32.4.57; 32.4.58+ kan legacy transition/hold niet adopteren.
- Legacy atomic authority via symlink/non-regular state wordt geweigerd.
- Verplichte acceptance case 3/4 aangescherpt naar echte CP direct-probe/bounded-blocker semantics.
- Laatste wijzigingen zijn statisch doorgelopen maar nog niet via pytest uitgevoerd; geen nieuwe GREEN-claim.
- Full BUILD_32457.py + exact fresh-extract blijft de eerstvolgende harde execution gate.
- Geen productieactie, nieuwe rescueketen, duplicaat 56-command of kandidaat-ZIP.

## 2026-09-18 — 32.4.57 checkpoint 8

- DETECTED-crashgrens gesloten: eerste persistente lifecycle-state is VERIFIED.
- Atomic pre-activation rollback ruimt uitsluitend de exact eigen candidate op en settle PREPARED naar ROLLED_BACK.
- 32.4.55 orphan Processing + stable corrupt Incoming recovery samengevoegd in de ene ReleaseController.
- Legacy ownership 50+ MB index: één streaming load + cached lookups; repeated-read klasse verwijderd.
- Definitieve `test_v32457_required_acceptance.py` bevat 15/15 architectuurauditcases plus twee 55-ingressregressies.
- BUILD_32457.py regenereert/controleert release-metadata vóór tests, controleert opnieuw na tests, bouwt alleen canonieke `EnergieProject_v32.4.57.zip` en herhaalt alle gates op exact fresh extract.
- Coverage-matrix 32.4.57: 12/12 live defectclusters en 11/11 historische contractfamilies structureel gemapt; execution blijft pending.
- Checkpoint 8: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_8_2026-09-18.md.
- Geen productieactie en geen kandidaat-ZIP.

## 2026-09-18 — 32.4.57 post-crash hardening

- Na chatcrash eerst persistent checkpoint/staging gelezen; checkpoint 6 én later opgeslagen overlaywerk teruggevonden. Geen herstart vanaf oud punt.
- Crash-resumeprotocol toegevoegd aan PROJECT_CONSTITUTION.md: “opnieuw” betekent eerst hoogste persistente state/checkpoint vinden.
- Canonical StateStore gehard tegen symlink/non-regular/corrupte reads.
- Future N→N+1 runtime-gap gesloten: Control Plane resync bij live-versiewijziging en controller self-reexec pas na COMPLETE.
- Historische pre-57 mode_entrypoint fixture toegevoegd.
- Historische 32.3.14/32.4.51/32.4.54 implementation-tests naar pre-57 fixture gemigreerd; testfamilies blijven behouden.
- 32.4.56 rescue identity-regressie aangepast naar 32.4.57/PM rc45 met behoud van rc44-contract.
- 32.4.57 architecture/static tests uitgebreid voor state-symlink, CP-resync en self-reexec.
- Checkpoint 7: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_7_2026-09-18.md.
- Geen productieactie, nieuwe rescueketen of kandidaat-ZIP uitgevoerd.
- Full overlay/fresh-extract suite blijft open en is de eerstvolgende harde buildgate.

## 2026-09-18 — 32.4.57 architecture-first

- 32.4.56 blijft live en wacht op exact één bestaande protected Native-MCP reload; geen duplicaat aangemaakt.
- Bestaande Incoming-keten ontleed: watcher/installer/transition/hold vormden meerdere lifecycle-eigenaren.
- Nieuwe single-owner ReleaseController ontworpen met acht fasen en gescheiden status.
- Atomic swap blijft primitive; OS flock vervangt stale lock recovery.
- Release-scoped Native MCP authorization via Control Plane ontworpen en in overlay uitgewerkt.
- 56→57 exact legacy-install adoption toegevoegd voor de eenmalige migratie.
- PM/mode/handover/health ontkoppeld van oude transition/hold voor >=32.4.57.
- Definitieve overlay opgeslagen onder Data/03_Systeem/Projectmanager/Staging/32457_release_overlay.
- Bewijs tot nu: 34/34 + 10/10 + 2/2 GREEN; full overlay suite nog open.

# WORK_LEDGER — 32.4.56

## 2026-09-18 — rc43 → rc44
- Oude aangeleverde 32.4.56-ZIP geclassificeerd als rc43 read-only referentie; niet als release gepromoveerd.
- rc43 verzamelde 1.852 tests.
- Nieuwe rc44 live-rescue regressieset voegde exact 16 tests toe; totaal 1.868 tests.
- TDD-baseline bewezen: 16/16 nieuwe tests RED vóór implementatie.
- Structurele implementatie uitgevoerd voor publication permissions/rebuild, transition-ticket settlement, PROJECT_CR MAINTENANCE bridge, CLEARUP retry/hashcache, Project-CR deep-verify-efficiëntie, CR snapshot-scope, stale worker recovery en persistente continuïteitsdocumenten.
- Bestaande 32.4.56 process-workspace/root-hygiene/keep-1/startup-recovery behouden; niet opnieuw ontworpen.
- PROJECT_CR stale-marker recovery = 30 minuten; watcher executor timeout = 20 minuten; 10 minuten veiligheidsmarge.
- Broad-health race gesloten: executorresultaat wordt exact aan generation/phase/revision/ticket gebonden en settlement markeert de bewezen fase in `completed_phases` vóór doorgang.
- Historische Project-CR mockfixture aangepast aan het strengere onafhankelijke SHA/ZIP-readbackcontract; productiecontrole is niet versoepeld.
- `NEXT_CHAT_V7.md` verwijderd; PROJECT_CONSTITUTION.md, CURRENT_HANDOVER.md en WORK_LEDGER.md zijn de persistente nieuwe-chatlagen.
- Geen productieactie uitgevoerd tijdens build.

## Testbewijs vóór finale document-sync
- Nieuwe live-rescue regressies: 16/16 GREEN.
- Volledige `test_v32456_*` familie: 39/39 GREEN.
- Relevante historische transition/32.4.55/CR-regressies GREEN.
- Volledige collectie: 1.868 tests.
- Volledige regressie in gesplitste, time-outbestendige batches: 1.866 passed, 2 skipped, 0 failed.
- Eerste canonical artifact telde exact 494 ZIP-members en doorstond dezelfde fresh-extract regressie volledig; daarna is uitsluitend deze handover/ledger-eindstatus bijgewerkt.

## Finale acceptatiegates
- [x] 16/16 nieuwe regressies GREEN.
- [x] 39/39 32.4.56-familie GREEN.
- [x] volledige 1.868-test suite GREEN (1.866 passed, 2 skipped).
- [x] finale canonical ZIP na deze laatste document-sync: manifest + SHA256SUMS + CRC GREEN (exacte SHA in externe werklog).
- [x] finale exact-ZIP fresh-extract: 1.866 passed, 2 skipped, 0 failed (bewijs in externe werklog).
- [ ] daarna live end-to-end releaseacceptatie, uitsluitend na expliciete productieautoriteit.


## 2026-09-19 — 32.4.57 checkpoint 12
- hervat vanaf werkelijk laatste persisted punt (checkpoint 11 bevestigd vóór wijziging)
- Native stale exact release-request cleanup toegevoegd + regressietest
- PM/orchestrator bevestigd CONTROLLER_OWNED vanaf 57; mode/validation geen Incoming-authority
- open gate: HA/GitHub volgorde t.o.v. atomic ACCEPTED moet vóór release-seal expliciet worden gekozen/getest
- geen productie-write, geen containerrestart, geen terminal, geen release-ZIP gebouwd
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_12_2026-09-19.md


## 2026-09-19 — 32.4.57 checkpoint 13
- checkpoint 12 bevestigd als laatste persisted bronpunt vóór hervatting
- HA/ACCEPTED-volgorde niet opnieuw ontworpen; latere checkpoints 5/6 zijn leidend
- 57 pm-startup-recovery Supervisor-restartpad verwijderd; PM thread supervision blijft
- nieuwe architectuurregressie toegevoegd; 38 specifieke 57 architectuurtests aanwezig
- geen productie-write, geen containerrestart, geen terminal, geen release-ZIP
- volgende gate: 56->57 HA bootstrap + build/test/fresh-extract
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_13_2026-09-19.md


## 2026-09-19 — 32.4.57 checkpoint 14
- live 56 HA publisher/rebuild route read-only bevestigd als 56->57 bootstrap
- geen extra HA daemon toegevoegd; bestaande handover hergebruikt
- architectuurtest toegevoegd; 39 specifieke 57 architectuurtests aanwezig
- geen productie-write, geen containerrestart, geen terminal
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_14_2026-09-19.md


## 2026-09-19 — 32.4.57 checkpoint 15
- live 56->57 Incoming bootstrap blocker bewezen: atomic LIVE_ACCEPTANCE + niet-terminale legacy transition blokkeren preflight
- een Native reload alleen is niet bewezen voldoende; latere 56 CR/CLEARUP/hygiene fasen kunnen opnieuw blokkeren
- vervolg beperkt tot veilige bestaande terminal/supersede/cancel-route in 56
- geen productie-write, geen restart, geen terminal
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_15_2026-09-19.md


## 2026-09-19 — 32.4.57 checkpoint 16
- crash-resume regel toegepast; checkpoint 15 bevestigd als laatste inhoudelijke bronstand
- 56 release_recover/cancel/supersede routes onderzocht: geen bestaande veilige transition-terminalisatie API
- compacte attempt_release_hold validatie kan atomic/hold sluiten zonder Native/CR/CLEARUP/hygiene als directe gate
- geen actieve oude release-owned tasks voor 54/55/56
- volgende exacte stap: evidence-bound, exact 56->57 legacy-transition supersede/finalize brug ontwerpen + TDD
- geen productie-write, geen restart, geen terminal, geen tweede Native request
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_16_2026-09-19.md


## 2026-09-19 — definitieve nieuwe-chat overdracht
- FINAL_HANDOVER_32.4.57_EXACT_RESUME_2026-09-19.md opgeslagen
- SHA256 56daa4d280ec4069a8143620c2ee28ea93ec22f651a526ab89c63d2e7d6ba847
- exact resume point = eenmalige 56->57 bootstrap/migratiehelper ontwerpen; daarna buildgate
- nieuwe chat niet opnieuw laten zoeken; starten bij §13 van final handover


## 2026-09-19 — 32.4.57 checkpoint 20
- eenvoudseis 57 vastgezet: één controller/één truth/één Incoming->GitHub/HA keten
- modes + CR/NAS CR/CLEARUP/hygiene behouden maar release-neutraal voor steady-state 57
- eenmalige evidence-bound 56->57 bootstrap helper in staging geschreven
- 12 nieuwe TDD regressies geschreven; niet uitgevoerd in huidige connector
- geen productie-write, restart, terminal of tweede Native request
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_20_2026-09-19.md


## 2026-09-19 — 32.4.57 checkpoint 21
- eenmalige 56->57 bootstrap statisch gehard + crash recovery
- 14 nieuwe tests aanwezig, niet uitgevoerd
- steady-state eenvoud audit afgerond: één controller, mode/CR/CLEARUP/hygiene release-neutraal
- geblokkeerd op uitvoerbare build/testomgeving met canonieke 56 ZIP binary
- geen productie-write/restart/terminal/Native side effect
- checkpoint: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_21_2026-09-19.md


## 2026-09-19 — checkpoint 22 continuation
- canonical 56 ZIP SHA exact bewezen
- lokale baseline batches 32.4.36 t/m 32.4.56 gericht GREEN waar afgerond; lange full suite alleen door 45s tool-timeout afgebroken, geen failure gezien
- modes blijven beschikbaar maar oude mode/hold transition workers zijn uit 57 release authority
- geen productie-write/restart/request

## 2026-09-19 — 32.4.58 prebuild GREEN
- canonical 32.4.57 buildbasis exact: SHA256 `6e81f14297d47a86f9dec896dcb69a0314dd45ed6929ff356977a38d4d64a2c9`.
- 11/11 nieuwe 58 simplification TDD-contracten GREEN.
- actieve releaseflow ontkoppeld van legacy adoption, globale mode/hold, auto-CLEARUP en oude watcher-authority.
- HA delivery route gewijzigd naar ondersteunde Supervisor store reload + self rebuild met benodigde app-permissies.
- PM health/snapshot false-positive cascade gerepareerd en healthdomeinen gescheiden.
- historische implementatiecontracten behouden via exacte canonical 57 fixtures; actieve 58-runtime niet teruggedraaid.
- actuele volledige collectie exact 1932 nodes: 1930 passed, 2 skipped, 0 failed.
- productie niet gewijzigd; live 58 E2E wacht op final artifact + fresh-extract GREEN + expliciete autorisatie.
- hoogste prebuild checkpoint: `ARCHITECTURE_32458_CHECKPOINT_27_2026-09-19.md`.


## 2026-09-19 — 32.4.58 prebuild GREEN
- Exact canonical 32.4.57 artifact SHA256 `6e81f14297d47a86f9dec896dcb69a0314dd45ed6929ff356977a38d4d64a2c9` als enige buildbasis gebruikt.
- 58 runtime vereenvoudigd: één ReleaseController; legacy adoption uit normale flow; evidence dedup; globale mode-startup/GUI weg; automatische CLEARUP weg; controller-runtime als livenessauthority.
- HA delivery naar ondersteunde Supervisor route `/store/reload` + `/addons/self/rebuild`; add-on heeft `hassio_api: true` en `hassio_role: manager`.
- PM health domeingescheiden; lege quarter snapshot geeft geen valse live-source cascade.
- Historische implementatiecontracten exact behouden via `tests/fixtures/legacy57`; actieve 58 runtime niet teruggebogen voor oude tests.
- Volledige actuele prebuild-suite: 1.943 passed, 2 skipped, 0 failed, totaal 1.945.
- Productie tijdens bouw ongewijzigd; geen restart/recreate/NAS-terminal/live state-edit/rescue/helper.
- Volgende gate: final artifact seal/build -> exact fresh-extract full suite -> expliciete live autorisatie.


## 2026-09-19 — 32.4.58 volledige prebuild-suite gesloten
- Actuele collectie exact 1.951 tests.
- Time-outbestendig in batches bewezen: 1.949 passed, 2 skipped, 0 failed.
- Alle 224 top-level testbestanden plus 3 geneste rapportgenerator-testbestanden volledig afgesloten.
- Productie ongewijzigd; geen restart/recreate, NAS-terminal, live state-edit of rescue/helper-script.
- Volgende harde gate: final metadata/manifest -> exact artifact -> fresh-extract suite -> expliciete live autorisatie.


## 2026-09-19 — 32.4.58 live N→N+1 defect + revised prebuild GREEN
- eerste final 58 artifact via Incoming correct geclaimd naar Processing; controller PID1 bleef live maar blokkeerde fail-closed in INSTALLING op rollback_unproven.
- root cause exact gereproduceerd: globale atomic journal stond nog ACCEPTED voor 56→57 en live 57 adapter behandelde die als fout voor 57→58.
- nieuwe RED-test toegevoegd voor exact direct-vorige ACCEPTED journal; tweede regressie houdt niet-aansluitende stale journals fail-closed.
- minimale structurele fix: alleen fysiek gereconcilieerde immediate predecessor ACCEPTED journal wordt historische evidence voor N+1.
- gerichte atomic/controller regressies GREEN.
- volledige revised collectie exact 1.953 tests: 1.951 passed, 2 skipped, 0 failed.
- live App blijft 32.4.57; oude artifact blijft Processing; geen state-edit, rescue/helper, extra restart of terminalreparatie.
- volgende gate: revised artifact build/seal + exact fresh-extract 1.953 tests.


## 2026-09-19 — 32.4.58 live recovery + final prebuild GREEN
- live 57→58 eerste run fail-closed op `rollback_unproven`; root cause vorige-release `ACCEPTED` atomic journal exact gereproduceerd.
- N→N+1 journal rollover-fix + evidence-bound blocked pre-activation self-recovery toegevoegd; 25 specifieke 58-regressietests GREEN.
- oude mislukte 58 generation en stale 57 publication fence reversibel gearchiveerd; geen current.json handmatig groen gezet.
- live 57-controller reconstrueerde zelfstandig naar `COMPLETE`; runtime `IDLE`, PID1, Incoming/Processing leeg.
- volledige actuele recovery-build collectie: 1.953 passed, 2 skipped, 0 failed, totaal 1.955.
- oude artifacts `c98c0806...` en `5419ba...` zijn vervallen.
- volgende gate: nieuw final 58 artifact bouwen/sealen -> exact fresh-extract 1.955 -> revised 58 via Incoming live E2E.
