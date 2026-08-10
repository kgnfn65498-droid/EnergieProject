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
