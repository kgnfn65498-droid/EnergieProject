# Development Build Contract — ontwerp 32.4.34

## Doel
Voorkom dat vaste ontwikkelafspraken bij een chatwissel, nieuwe Voice/Nomad-ingang of volgende build opnieuw worden vergeten. De Projectmanager moet één canonieke, machine-leesbare Development Build Contract-truth voeren en deze opnemen in status/handover/self-audit.

## Reikwijdte
Deze wijziging raakt alleen de Projectmanager-regielaag, handover/status en release-/self-auditcontracten. Geen wijziging aan energieproductiekern, maanddata, scheduler, rapportage of NAS-permissies.

## Canonieke eisen
Voor iedere release/build in DEVELOPMENT wordt vooraf vastgelegd en in iedere handover herhaald:
- denk-/ontwikkelsetting: MIDDEL of HOOG;
- release/build-id;
- Stap X/Y en totaal aantal geplande stappen;
- oorspronkelijke geschatte totale ontwikkeltijd;
- geschatte duur per stap;
- geplande test-/verificatietijd;
- verstreken actieve ontwikkeltijd;
- geschatte resterende tijd;
- werkelijk gemeten test-/verificatietijd waar beschikbaar;
- afwijking t.o.v. oorspronkelijke raming zonder de oorspronkelijke raming achteraf te herschrijven;
- planningstrend/leercurve.

Procesregels die dezelfde contract-truth draagt:
- autonoom ontwikkelen in geïsoleerde staging; productie niet autonoom wijzigen;
- TDD RED→GREEN en bekende fouten als regressies;
- audit/root-cause vóór structurele reparatie;
- schone staging + canonical builder + exact-artifact fresh-extract + atomic installatieproef vóór releasevrijgave;
- geen QNAP host-python3-aanname;
- geen onnodige Terminal/sudo/wachtwoordstappen voor Peter;
- geen autonome reboot/reset/destructief systeembeheer zonder expliciete opdracht;
- expliciete opslagopdracht = write + read-back-verificatie;
- roadmap/KB/open taken/afhankelijkheden controleren vóór claims als “klaar” of “wat hierna”;
- relevante chat/Voice/Nomad-intake naar PM/KB/roadmap/taken routeren en dedupliceren;
- ieder defect na bewezen oplossing terugschrijven naar KB + PM + regressietest/gate;
- chatwissel reset nooit bestaande afspraken, architectuur- of platformconstraints.

## Architectuur
Nieuwe module `projectmanager_v2/development_build_contract.py` bevat de contractversie, canonieke regels, normalisatie en evaluatie van buildmetadata. `TaskStore` kan buildmetadata opslaan zonder bestaande niet-build taken te breken. `progress_truth`, `handover`, `manager_service` en `self_audit` projecteren/evalueren dezelfde contract-truth. Release-/static tests bewijzen dat het contract aanwezig is en dat een build met ontbrekende verplichte metadata niet als contract-compliant kan worden aangemerkt.

## Compatibiliteit
Bestaande historische taken zonder buildmetadata blijven leesbaar. Alleen taken die expliciet als release/build worden gemarkeerd vallen onder de harde buildcontractcontrole; algemene USER/MAINTENANCE/operationele taken worden niet ten onrechte geblokkeerd.

## Acceptatie
- Nieuwe unittests gaan RED tegen 32.4.34 vóór implementatie.
- Contractevaluator faalt bij ontbrekende MIDDEL/HOOG, stappenraming of totale/testtijdschatting.
- Originele raming blijft immutable in voortgangsberekening.
- Handover bevat de volledige canonieke contract-snapshot zodat een nieuwe chat hem direct meekrijgt.
- PM-status en websurface tonen contractversie, setting, Stap X/Y, elapsed, ETA, testtijd en leercurve.
- Self-audit markeert een gemarkeerde development build zonder contractbewijs invalid.
- Volledige regressies + clean builder + exact fresh-extract + atomic 4.33→4.34 blijven verplicht.
