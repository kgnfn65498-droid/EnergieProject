# Changelog

## 8.8.0
- Verouderde retry-state wordt alleen opgeschoond wanneer aantoonbaar is dat de betreffende productiemaand definitief is afgerond of de retry uit een test/acceptatiesimulatie afkomstig is.
- Echte openstaande productie-retries worden nooit gewist door een geslaagde productietest.
- Nieuwe retry-metadata bewaart maand, reden en oorsprong van iedere toekomstige retry.
- Een succesvolle echte automatische maandafsluiting wist retry-tijd en retry-metadata expliciet.
- Scheduler-acceptatietest bewaart en herstelt ook de nieuwe retry-metadata.
- `Automatisch herstel` toont bij echte retries maand, tijdstip, oorsprong en reden.
- Schedulerroute, idempotency-beveiliging, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.7.0
- Duidelijkere scheduler-acceptatietekst met simulatiemoment, doelmaand, voorbereidende productietest en ongewijzigde schedulerinstelling.
- Nieuwe zichtbare status `Automatisch herstel` in de productiestatus.
- Bij blocked/error/failed wordt aangegeven of en wanneer een retry gepland staat.
- Definitief afgeronde maanden tonen dat een duurzame completion-marker aanwezig is.
- Geen wijziging aan schedulerroute, idempotency-beveiliging, rapportgeneratoren of Recovery Update.

## 8.6.0
- Duurzame idempotency-beveiliging voor echte automatische maandafsluitingen.
- Na een volledig geslaagde automatische run wordt atomisch een maandmarker opgeslagen in `automatic_completed_months.json`.
- De scheduler controleert deze marker vóór de gewone state en voert een reeds geslaagde maand daardoor niet opnieuw uit na een Home Assistant restart.
- Mislukte en geblokkeerde runs krijgen géén completion marker en blijven volgens de ingestelde retry opnieuw uitvoerbaar.
- Scheduler-acceptatietests gebruiken dezelfde productiecode maar schrijven nooit een echte completion marker.
- Append-only historie, productietest en rapportagecontract blijven ongewijzigd.

## 8.5.1
- Scheduler-acceptatietest voert na een upgrade automatisch eerst de verplichte veilige productietest van dezelfde softwareversie uit.
- Alleen na een geslaagde voorbereidende productietest wordt de echte schedulerroute gesimuleerd.
- De knop `Simuleer volgende scheduler-run nu` eindigt daardoor niet meer direct op `error` uitsluitend omdat de actuele versie nog niet productiegereed was.
- Scheduler Aan/Uit, planning en schedulerboekhouding blijven beschermd en ongewijzigd.
- Append-only historie registreert zowel de voorbereidende productietest als de scheduler-test afzonderlijk.
- Centrale maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.5.0
- Append-only automatische runhistorie in `automatic_run_history.jsonl`.
- Iedere productietest, scheduler-test en echte automatische run blijft afzonderlijk bewaard.
- Meerdere runs voor dezelfde maand overschrijven elkaar niet meer.
- Scheduler-simulaties worden niet dubbel als echte automatische run geregistreerd.
- Legacy-weergave blijft beschikbaar totdat de eerste v8.5-run is vastgelegd.

## 8.4.0
- Automatische historie onderscheidt `Test`, `Scheduler-test` en echte `Automatisch` runs.
- Historie toont softwareversie en eindcontrole.
- Scheduler-acceptatietest verifieert expliciet dat Aan/Uit ongewijzigd blijft.
- Productietrigger blijft `automatic`; onderscheid gebeurt uitsluitend in de auditlaag.
- Schedulerroute, maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.3.0
- Nieuwe scheduler-acceptatietest simuleert de eerstvolgende geplande automatische maandafsluiting direct.
- Productiescheduler en acceptatietest gebruiken exact dezelfde gedeelde executor.
- Acceptatietest gebruikt de echte due-beslissing en trigger `automatic`.
- Schedulerboekhouding en schedulerconfiguratie worden na de simulatie hersteld.
- Hierdoor kan de echte automatische route worden getest zonder te wachten op de volgende maand.

## 8.2.0
- P1-fix: Aan/Uit van automatische maandafsluiting wordt direct opgeslagen.
- Starten van de productietest kan daardoor geen niet-opgeslagen UIT-stand meer terugzetten naar de vorige AAN-stand.
- Productietest bewaakt de opgeslagen schedulerconfig byte-voor-byte en herstelt deze bij iedere onbedoelde wijziging.
- Finalization vereist exact de twee officiële outputbestanden.
- PDF-header en Recovery Update ZIP-integriteit worden gecontroleerd voordat automatische productie gereed wordt verklaard.
- Centrale maandworkflow en officiële rapportgeneratoren inhoudelijk ongewijzigd.

## 8.1.0
- Scheduler-runtimegate: na upgrade wordt een bewaarde AAN-stand pas uitvoerbaar na een geslaagde productietest van v8.1 zelf.
- Productiestatus onderscheidt ingestelde planning van werkelijk actieve scheduler.
- Datum/tijd van de volgende automatische run wordt leesbaar weergegeven.
- Nieuwe compacte historie van productietests en echte automatische maandafsluitingen.
- Centrale maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.0.0
- Start van de stabiele productielijn op basis van bewezen v7.9.0.
- Nieuwe centrale productiestatus in de operationele console.
- Automatische scheduler kan alleen AAN na een geslaagde productietest van dezelfde softwareversie.
- Console toont volgende automatische run en laatste definitieve output.
- Bestaande maandworkflow, rapportgeneratoren en Recovery Update blijven inhoudelijk ongewijzigd.

## 7.9.0
- Herstel workflow-triggercontract voor de veilige productietest.
- `automatic_test` is nu een geldige trigger naast manual, historical, automatic en resume.
- Productietest gebruikt dezelfde volledige maandworkflow als de automatische scheduler.
- Schedulerstatus blijft tijdens de productietest onaangeroerd.
- Geen wijziging aan rapportgeneratoren, Recovery Update of historische verwerking.

## 7.8.0
- Productieteststatus is versiegebonden; oude foutstatussen worden `Opnieuw testen`.
- Nieuwe productietest wordt direct als `running` zichtbaar vóór de achtergrondthread start.
- Nieuwe status `Automatische gereedheid`: pas groen na actuele preflight + workflow + finalization.
- Foutdetail van de laatste productietest is rechtstreeks zichtbaar in de console.
- Auditgeschiedenis blijft behouden; oude resultaten worden niet verwijderd.
- Onderliggende maandworkflow en rapportketen ongewijzigd.

## 7.7.0
- Duidelijke groene/grijze Aan/Uit-schakelaar voor automatische maandafsluiting.
- Planningvelden overzichtelijk gegroepeerd en knop hernoemd naar `Instellingen opslaan`.
- Workflowstartknoppen worden tijdens een actieve workflow uitgeschakeld.
- Hervatten wordt alleen aangeboden wanneer de laatste workflow echt is mislukt.
- Automatische status, preflight, finalization en productietest worden live bijgewerkt.
- Onderliggende maandworkflow en rapportketen ongewijzigd.

## 7.6.0
- Bedien automatische maandafsluiting rechtstreeks vanuit de operationele console.
- Aan/uit, dag, uur en retryperiode zijn instelbaar zonder handmatig configbestand.
- Veilige knop `Test automatische maandafsluiting nu`.
- Productietest gebruikt echte preflight, workflow en finalization maar verandert de schedulermaandstatus niet.
- Preflight-, finalization- en teststatus zichtbaar in de console.
- Bestaande maandworkflow en officiële rapportgeneratoren ongewijzigd.

## 7.5.0
- Productie-preflight vóór automatische maandafsluiting.
- Controle op lokale opslag, overdrachtsmap en rapport-runtime vóór een onbemande run.
- Geblokkeerde preflight start geen workflow en gebruikt de veilige retryperiode.
- Eindcontrole verifieert workflow, pre-report-validatie, rapportgeneratie, PDF en Recovery Update.
- Automatische maand wordt pas voltooid gemarkeerd als de volledige keten gereed is.

## 7.4.0
- Automatische Enphase-bronimport wanneer deze expliciet is ingeschakeld voor de actuele doelmaand.
- Nieuwe doelmaandgebonden eindvalidatie vóór overdracht en rapportage.
- Actuele rapportage wordt geblokkeerd als vereiste rapportinput onvolledig is.
- Historische runs blijven bronbeschikbaarheid-gestuurd en gebruiken geen actuele live-data als historie.
- Laatste pre-report-validatie wordt opgeslagen in status en workflowresultaten.

## 7.3.6

- Classificeert het bewust overslaan van live snapshots bij historische maanden als informatie in plaats van waarschuwing.
- Een foutloze historische run eindigt daardoor als `completed`; echte warnings blijven `completed_warning`.
- Geen wijzigingen aan import, rapportgeneratoren, Recovery Update of outputcontract.

## 7.3.6

- Classificeert een gecontroleerde historische rapport-skip als informatie in plaats van waarschuwing.
- Een geslaagde historische import zonder volledige detailbronnen eindigt nu als `completed`.

- Historische recovery doorzoekt nu ook recursief de echte maandboom achter `YYYY_MM als archief downloaden` (`/config/output/YYYY_MM`).
- Reeds bewaarde ZIP-archieven met de maandcode in de bestandsnaam worden automatisch als extra read-only bron ontdekt.
- Herstelde bestanden worden uitsluitend bij exact case-sensitive overeenkomende bestandsnaam overgenomen; niets wordt hernoemd.
- Bestaande doelbestanden worden nooit overschreven.
- Elke succesvolle historische bronrecovery wordt met bestandsnaam, bron en doel in het workflowlog vastgelegd.
- Actuele live snapshots worden niet gebruikt om historische maanden kunstmatig aan te vullen.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of vaste outputnamen.

## 7.3.1

- Historische workflow draait op de achtergrond en keert terug naar de operationele console.
- API-test keert na succes terug naar de operationele console.
- Bestaande `01_Input`-bestanden kunnen bij historische runs worden hergebruikt.

## 7.3.0

- Gewogen workflowvoortgang over acht hoofdphasen.
- Directe 0%-reset bij start, hervatten en historische run.
- Vloeiende voortgang, actieve stap, subactiviteit en indicatieve resterende tijd.

## 7.2.0

- Workflowmeldingen losgekoppeld van overdrachtsmeldingen.
- Start-/eindmeldingen en veilige automatische retry na mislukte maandafsluiting.

## 7.1.7

- Live workflowlog via `operation-status`.
- Statuspillen en gezondheidschecks verversen live.
- Zelftest toont leesbare tabel in plaats van ruwe JSON.

## 7.1.6

- Herstelt de JavaScript-syntax van de operationele console: newline-escapes in traceback- en logweergave worden nu correct als `\n` aan de browser geleverd.
- Daardoor werkt de 2,5-seconden polling van status, voortgang en live workflowlog weer daadwerkelijk.
- Live workflowlog scrolt na verversen automatisch naar de nieuwste regel.
- Geen wijzigingen aan backend-workflow, rapportgeneratoren, Recovery Update of outputcontract.

## 7.1.5

- Wis oude workflowfoutdiagnostiek direct bij de start van een nieuwe run.
- Zet de actuele runstatus op `running` en reset oude voortgang naar 0/0.
- Gezondheidsdashboard behandelt een normaal actieve workflow-lock niet langer als storing.
- Behoudt de v7.1.4-fix voor de dubbele `message`-parameter.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.4

- Herstelt de heartbeat-logaanroep die `message` zowel positioneel als benoemd doorgaf.
- `workflow_heartbeat()` schrijft de detailtekst nu als `heartbeat_message`, zonder botsing met het hoofdbericht van `append_workflow_log()`.
- Nieuwe statische regressietest controleert alle `append_workflow_log()`-aanroepen op dubbele `message`-argumenten.
- Geen wijzigingen aan workflowlogica, rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.3

- Workflowfouten bewaren stapnaam, fouttype, fouttekst, doorlooptijd en volledige Python-traceback.
- De operationele console toont de laatste workflowfout direct in een apart diagnoseblok.
- Het live workflowlog toont tracebacks en blijft automatisch verversen.
- Workflowlogs zijn downloadbaar via `download-workflow-log?month=YYYY_MM`.
- Succesvolle of gecontroleerd geannuleerde workflows wissen verouderde foutdiagnostiek.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

# Changelog

## 7.1.2
- Huidige kalendermaand vraagt nooit meer toekomstige dagen op bij SlimmeMeterPortal; verwerking stopt bij vandaag.
- Workflowstappen krijgen een bewaakte maximale looptijd; standaard 900 seconden.
- SlimmeMeterPortal maandimport schrijft per dag een heartbeat en voortgang naar het live workflowlog.
- Achtergrondworkflow heeft een failsafe die een achtergebleven workflow-lock altijd vrijgeeft.
- Staplog bevat voortaan looptijd en ingestelde timeout.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.1
- Gecontroleerde annulering is geen foutstatus of Python-traceback meer.
- Annuleringsreden wordt vastgelegd als `user_requested` of `service_shutdown`.
- Maandworkflow krijgt status `cancelled` en behoudt de add-on als draaiende service.
- Workflowlog, operationele status en Home Assistant-melding onderscheiden annulering van een echte fout.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.0
- Centrale knop voor maandverwerking start de volledige workflow op de achtergrond.
- Hervatten na een mislukte/onvolledige workflow hergebruikt reeds geslaagde stappen.
- Persistente workflowlog per maand met live weergave in de operationele console.
- Gezondheidsdashboard met compacte projectscore en technische deelcontroles.
- Workflow-lock blijft dubbele runs blokkeren; teller van geweigerde starts is zichtbaar via operation-status.
- Bestaande rapportketen, Recovery Update-contract en definitieve outputnamen ongewijzigd.

## 7.0.1
- Nieuwe operationele console boven de bestaande fase-7 workflow.
- Statuskaarten voor workflow, laatste maand, laatste run en automatische maandafsluiting.
- Live voortgangsweergave via bestaande status-endpoints, zonder nieuwe workflowlogica.
- Historische workflowresultaten als tabel met status, stappen, duur en mislukte stap.
- Bediening logisch gegroepeerd; technische functies blijven beschikbaar onder diagnostiek/beheer.
- Bestaande rapportketen, Recovery Update-contract en outputnamen ongewijzigd.

## 7.0.0
- Fase-7 besturingslaag toegevoegd boven de bestaande maandworkflow.
- Optionele automatische maandafsluiting op instelbare dag en uur.
- Historische maandselectie via de Ingress-interface, zonder live snapshots aan oude maanden toe te voegen.
- Compact endpoint `operation-status` met actuele workflowstatus en recente maandhistorie.
- Bestaande rapportketen, bestandsnamen en Recovery Update-inhoud blijven ongewijzigd.

## 6.9.1
- Stabiele afsluiting van fase 6.
