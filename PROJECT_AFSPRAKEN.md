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
