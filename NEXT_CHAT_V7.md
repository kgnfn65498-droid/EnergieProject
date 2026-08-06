# Vervolg nieuwe chat — start versie 7.0

We werken verder aan het Energieproject voor Home Assistant Green.

## Stabiele basis
Gebruik `EnergieProject_v6.9.1.zip` als enige bronbasis. Versie 6.9.1 is de afsluiting van fase 6.

## Wat al werkt
- SlimmeMeterPortal maandimport voor elektriciteit en gas
- HomeWizard detectie en koppeling met Home Assistant-namen
- Home Assistant energiesnapshot met Enphase, Nordpool en NextEnergy
- Opbouw van `01_Input/YYYY_MM`
- Centrale validatie
- Overdracht naar `/share/Energie_Overdracht`
- Drie officiële rapportgeneratoren
- Samenvoegen tot een rapport van 13 pagina's
- `Recovery_Update_YYYY_MM.zip`
- Publicatie naar `02_Output/YYYY_MM`
- SHA-256-eindcontrole
- Retentie, compacte samenvatting en workflow-locking
- Voorcontrole van alle verplichte rapportinputbestanden

## Uitgangspunten voor versie 7.0
1. Breek de werkende rapportketen niet.
2. Houd de definitieve output exact:
   - `Energierapport_YYYY_MM.pdf`
   - `Recovery_Update_YYYY_MM.zip`
3. Recovery Update bevat uitsluitend:
   - `03_Systeem/`
   - `04_Scripts/`
4. Geef bij iedere build:
   - een downloadbare ZIP
   - een committekst
   - het aantal geslaagde tests
   - één korte teststap tegelijk
5. Ontwikkel daadwerkelijk vanuit de aangeleverde ZIP; geef geen ontwerptekst in plaats van een build.

## Eerste doel voor 7.0
Ontwerp en bouw een nette fase-7 architectuur voor automatische maandafsluiting, historische maandselectie en een overzichtelijke operationele status, met behoud van volledige achterwaartse compatibiliteit.
