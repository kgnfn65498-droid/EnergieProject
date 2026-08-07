# Changelog

## 7.3.2

- Historische maandverwerking zoekt bestaande maandbestanden in lokale `01_Input`, het overdrachtspakket en `01_Input_YYYY_MM.zip`.
- Bestanden worden uitsluitend met exact dezelfde case-sensitive naam hergebruikt; niets wordt automatisch hernoemd.
- Bestaande doelbestanden worden nooit overschreven.
- Actuele live snapshots worden niet gebruikt om historische maanden kunstmatig aan te vullen.
- Maandvalidatie rapporteert bij ontbrekende bestanden ook welke historische bronpaden zijn gecontroleerd.
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
