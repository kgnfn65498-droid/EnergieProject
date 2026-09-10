# Roadmap v10.x

## Afgerond
- v10.4.x: automatische QNAP ZIP-installatie.
- v10.5.0-v10.5.1: Home Assistant-ontwikkeling hervat en releasefasen zichtbaar.
- v10.5.2: GitHub Deploy Key en publisher toegevoegd.
- v10.5.3: publisherlogging, persistente status en automatische UI-status bewezen.
- v10.5.4: definitieve end-to-end productietest zonder Terminal.
- v10.5.5: eerste conversatie-/analysebasis met gestandaardiseerde maand-, kwartaal- en jaarcontext.
- v10.5.6: analysebasis bruikbaar gemaakt in de productieconsole met sneloverzicht, download en expliciete datakwaliteit.
- v10.5.7: bestaande EPEX-maandbestanden toegevoegd als historische prijscontext zonder ongefundeerde all-in kostenberekening.

## Vervolg v10.5
- Analysecontext stapsgewijs uitbreiden met alleen bewezen bruikbare historische financiële/prijscontext.
- Geen nieuwe architectuur of databron toevoegen zonder direct projectvoordeel.

## Daarna
- v11: proactieve energieassistent op basis van de gevalideerde analysecontext.

- v10.5.8: EPEX-analyse gekoppeld aan de echte productiebron `05_Maanddata/EPEX`, inclusief dekking en bronhiaten.

- v10.5.9: EPEX-padresolutie robuust gemaakt voor de Home Assistant-projectmount en zichtbaar gemaakt in analysedata.

- v10.5.10: EPEX gekoppeld aan de feitelijke Energie_NAS-root (`05_Maanddata/EPEX`).

- v10.5.11: release-watcher race condition opgelost met atomische singleton-lock en veilige processing-quarantaine.

- v10.5.12: EPEX-autodetectie over Home Assistant `/share` en `/media`.

- v10.5.13: SMB/Finder-safe ZIP-stabiliteitscontrole vóór release-installatie.

- v10.5.14: terminalvrije watcher-self-refresh en EPEX read-only MCP-brug.

- v10.5.15: pre-installer ZIP-integriteitsgate voor Finder/SMB uploads.

- v10.5.16: EPEX bronbereikbaarheid en maandbeschikbaarheid expliciet gescheiden.

- v10.5.17: release-watcher als zelfstandige auto-restart Container Station-service.

- v10.5.18: eerste financiële context met dekkinggestuurde marktvariabele kosten.

- v10.5.19: NextEnergy-contractcontext en live leverancier-prijstelemetrie.

- v10.5.20: historische NextEnergy-prijsreeks uit Home Assistant kwartier-snapshots.

- v10.5.21: historische NextEnergy-prijsreader via NAS/MCP productiepad.

- v10.5.22: verbruikgewogen NextEnergy-afnameprijs en geobserveerde importkosten.

- v10.5.23: verbruikgewogen NextEnergy-kosten geïntegreerd in financiële maandstatus.

- v10.5.24: geobserveerde financiële run-rate en meetduur als basis voor betrouwbare prognoses.

- v10.5.25: robuuste volledige-JSON kwartierreader + regressieherstel gewogen NextEnergy-analyse.

- v10.5.26: structureel herstel MCP snapshotreader met echte toolnamen en permanente diagnostiek.

- v10.5.27: runtimefix timezone na bewezen succesvolle MCP snapshotreader.

- v10.5.28: prognosekwaliteitsdrempel op echte NextEnergy/P1-waarnemingen; geen voortijdige extrapolatie.

- v10.5.29: meetdekking/prognosegereedheid als expliciete voortgangs-KPI.

- v10.5.30: v10.6 30-dagen variabele-stroomprojectie voorbereid achter kwaliteitsgate.

- v10.5.31: kandidaatprojectie voor validatie vóór gate-open; officiële prognose blijft geblokkeerd.

- v10.5.32: release-/runtime-diagnostiek in Web UI; geen losse NAS/Container Station-logs meer nodig bij releaseproblemen.

- v10.5.33: financiële readiness-matrix + veilige voorschotcontext richting v10.6.

- v10.5.34: gevalideerde contractkosten-ingangslaag voor vaste kosten, opslag, terugleververgoeding en gasformule.

- v10.5.35: daadwerkelijke leveranciercomponentberekening + dynamische terugleverformule voorbereid.

- v10.5.36: contractformulemotor voor terugleververgoeding en gas, nog gated vóór all-in activatie.

- v10.5.37: zichtbare rapportpagina in Home Assistant GUI hersteld.
- Nog gepland tot v10.6.0: v10.5.39 consolidatie/acceptatie → v10.6.0 financiële productierelease.

- v10.6.0: financiële 30-dagen productieprognose geactiveerd achter de 7-dagen kwaliteitsgate; leverancier-all-in blijft contract-gated.
- Resterend tot v11.0: 4 productiestappen gepland: v10.6.1 contract/all-in validatie, v10.7 prognose-engine verdieping, v10.8 officiële rapportgenerator-integratie, v10.9 eindvalidatie/consolidatie.

## v25 — gevalideerde besparingsboekhouding
- v25.0.0 — stap 1/5: Savings Ledger Runtime; uitsluitend gemeten en gevalideerde gerealiseerde besparingen boekbaar, zonder dubbeltelling.
- v25.1.x — stap 2/5: cumulatieve portfolio-impact over gevalideerde acties.
- v25.2.x — stap 3/5: guarded impact op maandbudget/voorschotcontext.
- v25.3.x — stap 4/5: officiële rapportpublicatie van gevalideerde cumulatieve besparing.
- v25.4.x — stap 5/5: completion/consolidatie, externe datagates mogen gesloten blijven.


## v31 — chat/voice-laag
- v31.0.0 — stap 1/4 + 2/4 gebundeld: Conversation Context Runtime + Conversation Intent Runtime.
- v31.1.x — stap 3/4: guarded Conversation Response Runtime voor gewone-taaluitleg, diagnose en aanbevelingen.
- v31.2.x — stap 4/4: chat/voice completion + rapport-/print-handoff zonder externe uitvoering.
- Daarna v32: eindintegratie, backup/recovery, eindvalidatie en alleen fixes in v32.x.

- v31.1.0 — stap 3/4 gerealiseerd: guarded Conversation Response Runtime.
- Volgende: v31 stap 4/4 chat/voice completion + rapport-/print-handoff.

- v31.2.0 — stap 4/4 gerealiseerd: Chat/Voice Completion + Report/Print Handoff.
- v31 is compleet na Home Assistant-validatie.
- Volgende: v32.0.0 eindintegratie, backup/recovery en eindvalidatie; daarna alleen gerichte fixes.

## v32 — eindintegratie en afronding
- v32.0.0 — stap 1/3: Final Integration Runtime.
- v32.0.0 — stap 2/3: Backup/Recovery Runtime.
- v32.0.0 — stap 3/3: Final Validation Gate.
- Na succesvolle Home Assistant-validatie is de huidige roadmap afgerond.
- Daarna alleen gerichte v32.x fixes of een expliciet nieuw roadmapbesluit.

## v32.4.16 — closure releaseketen en ontwikkelproces
- [x] Root cause live incoming-block vastgelegd: één wachtende opvolgende ZIP maakte de huidige LIVE_ACCEPTANCE acceptance zelf onmogelijk.
- [x] Fail-closed acceptancecontract: exact één wachtende ZIP + huidige geldige LIVE_ACCEPTANCE mag zichzelf sluiten; andere niet-groene health blijft blokkeren.
- [x] Normale keten blijft `incoming -> processing -> processed`; geen `release_hold_tmp` als productfunctionaliteit.
- [x] Knowledge Base/ontwikkelafspraken bevatten root cause, structurele fix en verplichte regressiepreventie.
- [x] Packaging-regressie vastgelegd: geen cache/junk in release-artifact en preflight met productie-equivalente atomic ZIP-validatie verplicht.
- [ ] Live bewijs door gebruiker: 32.4.16 ZIP in incoming, automatische installatie, processed en daarna GUI actief melden.

## v32.4.17 — live closure defects uit 32.4.16

- [x] Watcher-hoofdlus begrensd tegen hangende externe helper/gate.
- [x] Historische publisher-state release-scoped gemaakt.
- [x] Eigen release-validation-hold/PM-health deadlock doorbroken zonder algemene health-bypass.
- [x] Knowledge Base/ontwikkelproceslessen bijgewerkt met root causes en regressiepreventie.
- [ ] Live bewijs: 32.4.17 installeert normaal vanuit `incoming`, eindigt zelfstandig op `ACCEPTED`, hold wordt vrijgegeven, watcher-heartbeat blijft fresh en GitHub-publicatie is current.
- [ ] Daarna opvolgende ingress zonder handmatige accept/hold-route bewijzen.
## v32.4.18 — structurele Incoming/Acceptance closure

- [x] Root cause `inactive hold + LIVE_ACCEPTANCE` vastgelegd en restart-safe recovery ontworpen.
- [x] Transactievolgorde omgedraaid: eerst atomic `ACCEPTED`, daarna hold release; `active+ACCEPTED` is herstelbaar.
- [x] Canonieke version-scoped GitHub-publicatiestatus uit Home Assistant publisher; legacy NAS-state alleen fallback.
- [x] Watcher hard bounded met SIGTERM -> grace -> SIGKILL.
- [x] TDD-regressies voor beide restartvensters, fail-closed ongeldige state, publisher truth en harde watcher-timeout.
- [x] Live-audit: operationele `current_quarter_hour_snapshot` RED ontkoppeld van release-acceptance; release-specifieke RED/ORANGE blijft fail-closed.
- [ ] Live bewijs: 32.4.18 installeert uit `incoming`, publiceert, sluit autonoom naar `ACCEPTED`, hold eindigt inactive en watcher-heartbeat blijft fresh.
- [ ] Daarna opvolgende release/incoming zonder handmatig accept-commando bewijzen.



## v32.4.19 — watcher heartbeat truth / Incoming closure
- [x] Root cause: verse PM-cycli lazen watcher-liveness via stale mount-mtime terwijl heartbeat-payload vers was.
- [x] Heartbeat-payload wordt canonieke liveness-truth; mtime alleen fallback.
- [x] `mode_allows` bewaart echte returncodes; rc=3 denial wordt niet als timeout/fout gelogd.
- [x] Live audit uitgevoerd: 32.4.19 bleef geblokkeerd door cross-host clock skew; root cause doorgeschoven en structureel gerepareerd in 32.4.20.

## v32.4.20 — clock-skew closure / Incoming definitief
- [x] Live root cause bewezen: QNAP-watcher en HA/PM hadden circa 16–17 minuten wall-clock skew; PM markeerde een daadwerkelijk pulserende watcher daardoor RED.
- [x] Clock-onafhankelijke heartbeat pulse-probe toegevoegd; stale/future absolute epoch wordt niet blind vertrouwd.
- [x] Geen heartbeatverandering binnen begrensd probevenster blijft fail-closed RED.
- [x] TDD voor positieve/negatieve skew, levende/dode watcher en release-acceptance met bewezen puls.
- [ ] Live bewijs: 32.4.20 sluit autonoom `LIVE_ACCEPTANCE -> ACCEPTED`, hold wordt inactive en volgende ingress wordt vrijgegeven zonder bootstrap.



## v32.4.21 — self-audit provenance / Incoming closure

- [x] Live root cause 32.4.20 vastgesteld: watcher GREEN en publicatie GREEN, maar hold blokkeerde op `projectmanager self-audit stale versus current PM status`.
- [x] Onmogelijke mtime-invariant verwijderd voor 32.4.21+: audit is door PM-finalisatie per ontwerp eerder geschreven dan de laatste statusrewrite.
- [x] Expliciete status-generatieprovenance toegevoegd en fail-closed getest.
- [x] Zes reeds aanwezige 32.4.20 SMB-heartbeattests die de artifactcode niet haalde gecorrigeerd door de ontbrekende stabiele-inode/v2-implementatie toe te voegen; tests niet verwijderd.
- [x] Live bewijs 2026-09-09: 32.4.21 sloot autonoom `LIVE_ACCEPTANCE -> ACCEPTED`; hold werd door `projectmanager_auto` inactive en alle release-health werd GREEN zonder bootstrap.


## v32.4.22 — CLOSED-maand startup-idempotency

- [x] Root cause: na app-restart kon de automatische scheduler vóór startup recovery een maand evalueren; `automatic_month_close_due()` kende alleen lokale HA completion/state en niet de canonieke RecoveryManager `CLOSED`-status.
- [x] RecoveryManager `CLOSED` blokkeert een automatische rerun ook wanneer lokale completion-state ontbreekt.
- [x] Startup recovery-gate toegevoegd: automatische maandafsluiting wordt pas geëvalueerd nadat recovery/reconciliation is teruggekeerd; bij exception blijft de gate dicht.
- [x] Handmatige workflow, imports, sampling en release-closure blijven ongewijzigd.
- [ ] Live bewijs: restart/update met augustus `CLOSED` veroorzaakt geen nieuwe automatische augustus-maandafsluiting.

## v32.4.23 — audit-closure vóór ngrok en 32.5

- [x] Maandclosure-truth gehard naar `CLOSED_VALID / OPEN / UNKNOWN`; UNKNOWN is fail-closed voor automatische mutaties.
- [x] Eén deep-verified CLOSED-predicate en verse dynamische RecoveryManager-status; scheduler, preflight en executor hebben onafhankelijke safety-gates.
- [x] Startup readiness en productiecertificering gekoppeld aan productiekern `9.4-core2`; release-hold is certificaatbewust.
- [x] Canonieke roadmap-validator detecteert dependency-cycles en semantische verplichte gates.
- [x] ngrok-besluit vastgelegd: behouden als externe PM-poort, alleen via dedicated authenticated route; volledige 8099 exposure verboden.
- [x] `voice-live-acceptance` staat als verplichte gate vóór 32.5/Cowork.
- [x] `new-chat-handover-live` staat als verplichte gate vóór 32.5/Cowork.
- [ ] Live acceptance na installatie: CLOSED augustus blijft onaangeroerd bij restart, core2-certificering is actueel en release sluit autonoom.
- [ ] Daarna ngrok edge-policy/OAuth/JWT/rate-limit configureren en echte Voice/ChatGPT/Nomad E2E accepteren; pas daarna 32.5/Cowork.



## v32.4.24 — maintenance-closure na live 32.4.23

- [x] Legacy CLOSED/lifecycle-conflict kan niet meer als OPEN door de schedulergrens.
- [x] Onbereikbare secundaire closure-truth bij Recovery-OPEN faalt gesloten.
- [x] Productiekern `9.4-core3` kan non-mutating worden gecertificeerd zonder een echte maand opnieuw te verwerken.
- [x] Roadmap-migratie veroorzaakt geen startup-crash bij read-only directory-permissies.
- [ ] Live acceptance na installatie: core3-certificaat geldig, augustus blijft CLOSED, juli blijft geblokkeerd, release-hold/atomic GREEN.
## 32.4 closure — 32.4.36
- 32.4.36: CR max-1 + canonieke naamgeving + lokale QNAP NAS-CR + fresh CLEARUP dependency-audit closure.
- Na live 32.4.36/CLEARUP-acceptatie blijft de bestaande volgorde: ngrok security → Voice Mode live acceptance → new-chat/handover live acceptance → 32.5/Cowork.
- Geen van deze vervolgstappen is onderdeel van 32.4.36.

