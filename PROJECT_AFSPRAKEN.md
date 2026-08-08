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
