# Changelog

## 7.3.1

- Historische maandverwerking hergebruikt bestaande 01_Input-bestanden wanneer live snapshots bewust worden overgeslagen.
- Historische workflow start op de achtergrond en keert direct terug naar de operationele console.
- API-verbindingstest keert na een geslaagde test direct terug naar de operationele console.
- Hervatten kan vanaf een mislukte historische workflow de eerder geslaagde stappen hergebruiken.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of vaste outputnamen.

# 7.3.1

- Gewogen workflowvoortgang op basis van gemeten stapduur.
- Voortgang reset direct naar 0% bij start/hervatten/historische run.
- Vloeiende animatie tijdens lange stappen.
- Actieve stap, detail en geschatte resterende tijd zichtbaar.
- Acht vaste hoofdphasen voor consistente actieve en historische visualisatie.
- Geen wijzigingen aan import-, rapport- of Recovery Update-logica.

- Workflowmeldingen zijn losgekoppeld van overdrachtsmeldingen.
- Optionele Home Assistant-melding bij start van een maandworkflow.
- Automatische maandafsluiting meldt start, succes, annulering en fouten herkenbaar als automatische run.
- Automatische maandafsluiting wacht standaard 6 uur na een mislukte poging voordat opnieuw wordt geprobeerd; geen retry-lus meer.
- Operationele status bevat workflow-trigger en informatie over de volgende automatische retry.
- Rapportketen, Recovery Update-contract en vaste outputnamen zijn ongewijzigd.

## 7.3.1

- Live workflowlog wordt rechtstreeks via `operation-status` aangeleverd en iedere 2,5 seconde in de console ververst.
- Statuspillen en gezondheidschecks verversen nu mee met de actieve workflow.
- De volledige zelftest toont een leesbare tabel met controles, status en details in plaats van ruwe JSON.
- JavaScript-syntax wordt opnieuw gecontroleerd op de daadwerkelijk gegenereerde console.
- Geen wijzigingen aan backend-workflow, rapportgeneratoren, Recovery Update of outputcontract.

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
