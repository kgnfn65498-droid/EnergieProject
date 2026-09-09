# Vaste ontwikkelafspraken Energieproject

- Als de gebruiker zegt `bouw X.Y`, bouw daadwerkelijk een complete nieuwe productieversie op de vorige geteste versie.
- Iedere build levert: complete ZIP, changelog, kopieerbare committekst en testinstructies onderaan.
- Na iedere versie wachten op de Home Assistant-testresultaten voordat de volgende versie wordt gebouwd.
- Terugkerende testhandelingen automatiseren; normaal beoordelen via één diagnosepakket. Screenshots alleen bij visuele/interactieve problemen.
- De iMac mag weken uitstaan en mag geen noodzakelijke schakel zijn in de productieketen.
- Productiedata, maandverwerking en back-ups moeten 24/7 via Home Assistant/QNAP kunnen doorlopen.
- Recovery Manager blijft primair voor echte calamiteiten/crash recovery; noodherstel moet met een korte actuele handleiding kunnen.
- Als een chat traag/vol wordt, wordt een chat-overdracht gemaakt met status, roadmap, afspraken en open acties.
- Grote architectuurkeuzes bij voorkeur eerst kort bespreken in een spraaksessie.
- Einddoel: vragen in gewone taal; data-inname, opslag, validatie, back-up en voorbereiding verlopen automatisch.
- Financiële analyse bewaakt termijnbedrag, werkelijke kosten, historische data, terugverdientijd en marktopties; geen ongefundeerde schattingen.
- Toekomstige analyse bevat weersverwachting, dynamische prijzen en proactieve energie-/investeringssignalen.

- Normale Home Assistant-releaseprocedure: app updaten/herstarten en GUI verversen. `Opnieuw opbouwen` alleen bij aantoonbare image-/cacheproblemen of buildlaagwijzigingen.
- Gewenste korte releaseflow: gebruiker downloadt release-ZIP en plaatst die uiteindelijk alleen in een vaste NAS-inbox; verdere validatie/verwerking wordt geautomatiseerd.
- Een NAS-migratie mag nooit blind bestanden verplaatsen: eerst inventaris, daarna hashcontrole, rollback en pas daarna opruimen.

## Release-uitvoering vanaf v10.4.1
- Installer en watcher mogen nooit afhankelijk blijven van een scriptbestand in de worktree die zij vervangen.
- Beide host-side processen verplaatsen hun actieve script daarom naar `/tmp` vóór releaseverwerking.
- Een release die tijdens worktree-verwijdering faalt moet automatisch uit de vooraf gevalideerde tar-backup herstellen.

## Release- en leercontract vanaf 32.4.16
- De normale releaseflow is uitsluitend: `incoming -> processing -> processed`; tijdelijke hold-mappen of handmatige atomic accept-commando's tellen nooit als structurele oplossing.
- Een releaseclosure is pas groen nadat een opvolgende synthetische release tijdens/na acceptance automatisch kan worden opgepakt zonder gebruikersinterventie.
- Bij ieder defect worden symptoom, root cause, structurele fix en regressietest in de Projectmanager Knowledge Base vastgelegd.
- Tests die alleen de huidige release accepteren zijn onvoldoende voor ingress-closure; de volgende release moet onderdeel zijn van de E2E.
- Een release-ZIP wordt nooit rechtstreeks uit een door tests vervuilde werkboom gemaakt: eerst schone staging, expliciete uitsluiting van `.pytest_cache`, `__pycache__`, `.DS_Store`, `*.pyc` en `*.pyo`, daarna manifests, ZIP en tenslotte validatie met dezelfde atomic release-validator als productie.

## Release- en leercontract vanaf 32.4.17

- Een watchercontainer die `Up` is is geen bewijs van een gezonde watcher; heartbeat en voortgang moeten vers blijven.
- Externe helpers in een kritieke watcher-hoofdlus mogen nooit onbeperkt kunnen blokkeren; zij zijn bounded en fail-closed.
- Runtime-health is release-scoped: historische publisherfouten mogen een nieuwere bewezen release niet rood maken.
- Een safety-hold mag zijn eigen validatie niet circulair blokkeren. Alleen de exact verwachte eigen transition-state mag tijdelijk als acceptance-context gelden.
- Bij release-audits worden containerstatus, heartbeat, atomic state, hold, publisher/publication en volgende-ingress als één E2E-keten gecontroleerd.
- Packaging gebeurt uitsluitend vanuit een schone stagingboom; cache/junk is een harde releasefout.
## Release- en leercontract vanaf 32.4.18

- Release-hold en atomic journal worden als één herstelbare state-machine behandeld; alle relevante combinaties moeten na restart idempotent convergeren.
- Normale veilige closurevolgorde: validatie groen -> atomic `ACCEPTED` -> release-hold vrijgeven.
- `inactive hold + LIVE_ACCEPTANCE` mag alleen automatisch herstellen wanneer de persisted hold een normale eerdere validatie (`validation_status=ok`, `reconcile_status=ok`, geen emergency) bewijst en een verse validatie opnieuw groen is.
- GitHub-publicatie heeft één canonieke actuele statusbron per release. Historische statusbestanden mogen niet als actuele waarheid concurreren.
- Heartbeat-kritieke subprocessen hebben een harde bovengrens: TERM, korte grace, daarna KILL; fail-closed blijft verplicht.
- Voor closure zijn **twee opeenvolgende releases** plus restart/crash-vensters een verplichte regressie; alleen een losse current-release acceptance is onvoldoende.
- Release-acceptance mag niet gekoppeld zijn aan algemene energie-operatiehealth. Sensor-/kwartierdata-RED blijft zichtbaar en actionable, maar alleen release-chain health en de expliciete release-validatiechecks mogen de release-hold blokkeren.



## Release-health contract vanaf 32.4.19
- Een heartbeat-bestand met expliciete Unix-epoch payload gebruikt die payload als canonieke liveness-truth; NAS/SMB-mtime mag geen verse watcher tot RED degraderen.
- Een parseerbare stale heartbeat-payload blijft fail-closed RED, ook als bestandsmetadata vers is.
- Shell-gates bewaren de echte child-returncode voordat conditionele shellcontrol-flow die waarde kan overschrijven; capability-denial en technische fout worden verschillend behandeld.
- Release-closure wordt pas groen verklaard nadat live is bewezen dat `LIVE_ACCEPTANCE -> ACCEPTED` zonder handmatig accept-commando gebeurt en een opvolgende ingress wordt vrijgegeven.
## Release-health contract vanaf 32.4.20
- Liveness tussen verschillende hosts mag niet uitsluitend op absolute wall-clock timestamps worden gebaseerd; QNAP en Home Assistant kunnen klokskew hebben.
- Wanneer heartbeat-epoch stale of future lijkt, moet de collector een begrensde pulsverandering waarnemen. Een veranderende payload is clock-onafhankelijk bewijs dat de watcher leeft.
- Geen puls binnen het probevenster blijft fail-closed RED; clock-skew mag nooit worden omzeild door een algemene GREEN-exceptie.
- Release-closure mag pas doorgaan nadat watcher-liveness, publication, hold-state en atomic transition ieder via hun eigen broncontract zijn bewezen.
- Verschillende namespace-paden (`/share/...` in Home Assistant versus QNAP-lokaal) zijn geen split-brain wanneer zij dezelfde fysieke NAS-share representeren; filesystem-identiteit moet op bronmountniveau worden beoordeeld.

