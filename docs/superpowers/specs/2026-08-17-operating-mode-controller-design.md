# EnergieProject Operating Mode Controller — ontwerp

Datum: 2026-08-17
Status: GOEDGEKEURD ONTWERP
Basisrelease: v32.3.11
Doelrelease: eerstvolgende release na v32.3.11

## 1. Doel

De drie bedrijfsmodi van het EnergieProject worden geen labels maar afdwingbare bedrijfsprofielen. De Projectmanager wordt eigenaar van de modus, de bijbehorende systeemconfiguratie en de reconciliation tussen gewenste en werkelijk gemeten toestand.

Er blijven precies drie echte modi:

- `USER`
- `DEVELOPMENT`
- `MAINTENANCE`

Daarnaast bestaat één aparte instelling `automatic_switching_enabled`, standaard `true`. Dit is geen vierde modus.

## 2. Hoofdgedrag

`USER` is de normale rust- en productiestand. Wanneer automatische schakeling aanstaat, mag de Projectmanager op basis van de opdracht tijdelijk opschalen:

- normale vraag of normale energiewerking -> `USER`
- bouwen, wijzigen, testen of releasen -> tijdelijk `DEVELOPMENT`
- backup, herstel, cleanup, migratie of infrastructuuronderhoud -> tijdelijk `MAINTENANCE`

Na succesvolle afronding moet de controller de toestand reconciliëren en automatisch terugkeren naar de veilige basisstand, normaal `USER`.

Een handmatige moduskeuze in de GUI blijft mogelijk. Als automatische schakeling wordt uitgezet, blijft de gekozen modus vaststaan en mag de controller niet stilzwijgend opschalen.

## 3. Architectuur

### 3.1 Mode Controller

Eén centrale `OperatingModeController` beheert:

- gewenste basisstand;
- actuele effectieve modus;
- automatische schakeling aan/uit;
- reden van een tijdelijke overgang;
- vorige veilige modus;
- overgangsstatus;
- laatste succesvolle reconciliation;
- eventuele afwijkingen of herstelacties.

De controller is de enige geautoriseerde codepad voor mode-overgangen.

### 3.2 Desired state versus observed state

Iedere modus heeft een desired-state-profiel. Reconciliation vergelijkt dit met observed state van relevante services en instellingen.

Voorbeeld:

- desired: `USER`, release-watcher `OFF`
- observed: release-watcher `ON`
- actie: watcher stoppen, opnieuw meten, resultaat loggen

Een modewissel is pas geslaagd wanneer de gewenste toestand niet alleen geschreven maar ook teruggelezen en bevestigd is.

### 3.3 Projectmanager

Operating Mode Management + Reconciliation wordt een kerntaak van de Projectmanager. De Projectmanager controleert de toestand minimaal:

- bij startup/reboot;
- na een mode-overgang;
- na een release;
- na onderhoud/herstel;
- periodiek tijdens runtime;
- wanneer een inconsistente status wordt waargenomen.

Bij herstelbare drift corrigeert de Projectmanager automatisch. Bij niet-herstelbare drift blijft het systeem fail-safe, logt de fout en rapporteert de afwijking.

## 4. Modeprofielen

### 4.1 USER

Normale productie- en vakantestand.

Verwachte toestand:

- release/Incoming-watcher: `OFF`
- normale energie-import: `ON`
- geplande maandworkflow: `ON`
- automatische maandverwerking van de vorige volledige kalendermaand: `ON`
- automatische maandsluiting: `ON`, maar uitsluitend voor een volledig afgesloten kalendermaand
- rapportage en monitoring: `ON`
- normale gebruiksfuncties: `ON`
- build/test/release: `OFF`
- development-specifieke tijdelijke capabilities: `OFF`
- onderhoudscapabilities: beperkt tot veilige normale functies
- reconciliation: `ON`

Vakantie-eis: wanneer de gebruiker het systeem in USER achterlaat, moet begin van een nieuwe maand de vorige volledig afgesloten maand zelfstandig kunnen worden opgehaald, gevalideerd, verwerkt, gerapporteerd en gecontroleerd, mits alle vereiste bronnen beschikbaar zijn.

Een lopende maand mag nooit automatisch voortijdig worden gefinaliseerd.

### 4.2 DEVELOPMENT

Voor gecontroleerd bouwen, testen en releasen.

Verwachte toestand:

- release/Incoming-watcher: `ON`
- Incoming/releaseketen controleren bij binnenkomst in DEVELOPMENT
- build/test/release-capabilities: `ON`
- staging/test-schrijfacties: `ON` binnen bestaande scope en guards
- normale energie-import: `ON`
- geplande maandworkflow: `ON`
- rapportage/monitoring: `ON`
- maintenance-only acties: niet automatisch vrijgegeven
- reconciliation: `ON`

Development mag normale productieprocessen niet onnodig uitschakelen. Een concrete test mag een productieproces tijdelijk pauzeren, mits de vorige toestand wordt bewaard en bij exit wordt hersteld.

### 4.3 MAINTENANCE

Voor backup, recovery, cleanup, migratie en infrastructuuronderhoud.

Verwachte toestand:

- release/Incoming-watcher: `OFF`
- development/build/release: `OFF`
- backup/recovery/cleanup/migratie-capabilities: `ON` volgens bestaande safety gates
- normale energie-import: normaal `ON`
- geplande maandworkflow: normaal `ON`
- processen mogen alleen tijdelijk worden gepauzeerd wanneer de onderhoudstaak dit technisch vereist
- bij exit moeten tijdelijk gepauzeerde productieprocessen worden hersteld
- reconciliation: `ON`

Destructieve onderhoudshandelingen, zoals een restore die productie overschrijft, behouden hun bestaande extra veiligheids- en bevestigingsgates. Automatisch naar MAINTENANCE schakelen is geen toestemming om zulke gates te omzeilen.

## 5. Automatische overgang

### 5.1 Intentieclassificatie

De orchestration-laag classificeert een gebruikersopdracht als `USER`, `DEVELOPMENT` of `MAINTENANCE` intent.

Voorbeelden:

- "Hoeveel gas heb ik deze maand gebruikt?" -> USER
- "Bouw deze functie" -> DEVELOPMENT
- "Maak een backup" -> MAINTENANCE

### 5.2 Tijdelijke opschaling

Bij `automatic_switching_enabled=true`:

1. bewaar basisstand en observed state;
2. bepaal vereiste tijdelijke modus;
3. valideer overgangsgates;
4. pas desired state toe;
5. meet observed state;
6. voer taak uit;
7. voer exitchecks uit;
8. herstel basisstand;
9. reconcile en bevestig;
10. log de volledige overgang.

### 5.3 Fail-safe

Een overgang mag nooit eindigen in een ongedefinieerde halve toestand.

Bij mislukking:

- stop verdere privilege-uitbreiding;
- herstel waar mogelijk de laatst bekende veilige toestand;
- voorkeur voor veilige terugkeer naar USER wanneer dat verantwoord is;
- meet opnieuw;
- log exact wat wel en niet is hersteld;
- markeer afwijking zichtbaar in status/GUI/chat.

## 6. Reconciliation

Reconciliation bestaat uit drie stappen:

1. lees gewenste modus en profiel;
2. meet werkelijke service- en configuratiestatus;
3. corrigeer herstelbare afwijkingen en verifieer via readback.

Minimale observed-state-bronnen voor de eerste implementatie:

- release-watcher status;
- Incoming/releaseketenstatus;
- add-on planning `schedule_enabled`;
- full workflow `full_workflow_enabled`;
- automatische maandsluiting `automatic_month_close_enabled`;
- relevante tijdelijke pause/override-status;
- effectieve mode state en laatste overgang.

De bestaande release-watcher ondersteunt al `run`, `status` en `stop` en wordt hergebruikt. Bestaande maandworkflow-configuratie wordt eveneens hergebruikt; de mode-controller bouwt deze subsystemen niet opnieuw.

## 7. Status en GUI

De GUI toont permanent:

- basisstand;
- actuele effectieve modus;
- automatisch schakelen `AAN/UIT`;
- reden van tijdelijke modus;
- reconciliation-status;
- eventuele drift/herstelstatus.

Voorbeeld:

`Basis: USER | Actueel: MAINTENANCE | Auto: AAN | Reden: backup | Reconcile: OK`

Er komen bedieningen voor:

- USER
- DEVELOPMENT
- MAINTENANCE
- Automatisch schakelen AAN/UIT

`AUTO` wordt nadrukkelijk geen vierde modus.

## 8. Chatstatus

Bij relevante projectinteracties wordt een korte statusregel getoond, bijvoorbeeld:

`[MODE] DEVELOPMENT · AUTO AAN · basis USER`

Bij tijdelijke opschaling:

`[MODE] MAINTENANCE · AUTO AAN · basis USER · backup uitvoeren`

Bij drift:

`[MODE] USER · AUTO AAN · AFWIJKING: watcher actief · herstel actief`

De native ChatGPT-interface zelf wordt niet aangepast; dit betreft de tekstuele projectstatus in reacties en de permanente status in de EnergieProject/HA-GUI.

## 9. Persistentie en reboot

De gewenste basisstand en automatic-switching-instelling worden persistent opgeslagen.

Na reboot/crash:

1. lees persistente mode state;
2. ga niet blind uit van de vorige observed state;
3. meet services en configuratie opnieuw;
4. reconcile naar de gewenste veilige toestand;
5. publiceer nieuwe observed state.

Stale tijdelijke DEVELOPMENT- of MAINTENANCE-status mag niet stilzwijgend als geldig worden hervat zonder bijbehorende actieve taak/reden. Zonder geldige tijdelijke context valt de controller terug naar de persistente basisstand.

## 10. Logging en audit

Iedere overgang registreert minimaal:

- timestamp;
- initiator/intentie;
- basisstand;
- oude effectieve modus;
- nieuwe effectieve modus;
- reden;
- gewijzigde capabilities/instellingen;
- readback-resultaten;
- exitstatus;
- eventuele automatische herstelacties.

Projectmanager-status, relevante roadmap/statusinformatie en mode-state moeten na een definitieve overgang consistent zijn.

## 11. Acceptatietests

De implementatie is niet klaar voordat minimaal aantoonbaar is bewezen:

1. USER zet de release/Incoming-watcher werkelijk uit.
2. USER houdt normale import en maandworkflow werkelijk aan.
3. USER verwerkt uitsluitend een volledig afgesloten vorige maand automatisch.
4. DEVELOPMENT zet de watcher aan en maakt gecontroleerde build/test/release mogelijk.
5. MAINTENANCE zet development uit en maakt de bedoelde onderhoudscapabilities beschikbaar.
6. `USER -> DEVELOPMENT -> USER` herstelt de volledige vorige veilige productietoestand.
7. `USER -> MAINTENANCE -> USER` herstelt de volledige vorige veilige productietoestand.
8. Automatische intentiegestuurde opschaling werkt zonder voorafgaande GUI-actie.
9. Handmatige vaste modus met automatisch schakelen UIT wordt gerespecteerd.
10. Reboot/startup voert reconciliation uit en laat geen stale tijdelijke modus achter.
11. Een bewust aangebrachte herstelbare drift wordt automatisch gecorrigeerd.
12. Een niet-herstelbare drift wordt fail-safe gemeld en niet verborgen.
13. GUI-status komt overeen met observed state.
14. Chatstatus komt overeen met de effectieve mode state.
15. Een mislukte overgang kan niet stil eindigen in een halve privilege/configuratietoestand.

## 12. Scope eerste implementatie

Wel in scope:

- centrale mode-controller;
- drie modeprofielen;
- automatic switching;
- persistent state;
- reconciliation;
- watcher- en maandworkflowkoppeling;
- statusmodel;
- eenvoudige GUI-status/bediening;
- auditlog;
- unit/integratie/acceptatietests.

Niet in scope:

- verdere Nomad-functionaliteit;
- nieuwe crash-recoveryarchitectuur;
- volledige GUI-herbouw;
- drie gescheiden runtime/containeromgevingen;
- nieuwe maandworkflow-engine;
- omzeilen van bestaande destructive-action safety gates.

## 13. Ontwerpbesluit

Gekozen aanpak: **B — Mode Controller + Reconciliation**.

Afgewezen:

- A — alleen configuratieprofielen: onvoldoende robuust tegen drift.
- C — volledig gescheiden runtimeomgevingen: te complex en niet nodig voor het huidige doel.

De kernregel luidt:

> Een modus is pas actief wanneer de gewenste toestand is toegepast, de werkelijke toestand is teruggelezen en de Projectmanager heeft bevestigd dat beide overeenkomen.
